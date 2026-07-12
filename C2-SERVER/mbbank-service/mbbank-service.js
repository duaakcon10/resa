require('dotenv').config();
const express = require('express');
const cors = require('cors');
const { MB } = require('mbbank');

const app = express();
const PORT = process.env.PORT || 3000;
const HOST = process.env.HOST || '0.0.0.0';

app.use(cors());
app.use(express.json());

const authenticateApiKey = (req, res, next) => {
    const apiKey = req.headers['x-api-key'];
    if (!apiKey || apiKey !== process.env.API_KEY) {
        return res.status(401).json({ success: false, message: 'Unauthorized: Invalid API key' });
    }
    next();
};

let mb = null;
let lastLoginAt = 0;

function createClient() {
    if (!process.env.MBBANK_USERNAME || !process.env.MBBANK_PASSWORD) {
        console.warn('MBBank credentials missing (MBBANK_USERNAME / MBBANK_PASSWORD)');
        return null;
    }
    // CookieGMVN/mbbank API
    return new MB({
        username: process.env.MBBANK_USERNAME,
        password: process.env.MBBANK_PASSWORD,
        preferredOCRMethod: process.env.MBBANK_OCR || 'default',
        saveWasm: true,
    });
}

async function ensureClient() {
    if (!mb) mb = createClient();
    return mb;
}

async function loginMBBank() {
    try {
        const client = await ensureClient();
        if (!client) return { success: false, message: 'Init failed — missing credentials' };
        await client.login();
        lastLoginAt = Date.now();
        console.log('MBBank login successful');
        return { success: true, message: 'Login successful' };
    } catch (error) {
        console.error('MBBank login failed:', error.message);
        return { success: false, message: error.message };
    }
}

function isSessionExpired() {
    if (!lastLoginAt) return true;
    // re-login every ~8 minutes
    return Date.now() - lastLoginAt > 8 * 60 * 1000;
}

async function ensureValidSession() {
    if (!mb || isSessionExpired()) {
        console.log('Session expired or missing, logging in...');
        const r = await loginMBBank();
        if (!r.success) throw new Error(r.message || 'login failed');
    }
}

function formatDate(date) {
    const day = String(date.getDate()).padStart(2, '0');
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const year = date.getFullYear();
    return `${day}/${month}/${year}`;
}

function normalizeTx(tx) {
    if (!tx || typeof tx !== 'object') return null;
    // mbbank lib fields vary slightly across versions
    const credit = Number(
        tx.creditAmount ?? tx.amount ?? tx.credit ?? 0
    ) || 0;
    const debit = Number(tx.debitAmount ?? tx.debit ?? 0) || 0;
    const amount = credit > 0 ? credit : (debit > 0 ? -debit : Number(tx.amount) || 0);
    return {
        creditAmount: credit > 0 ? credit : (amount > 0 ? amount : 0),
        amount: credit > 0 ? credit : amount,
        description: tx.description || tx.transactionDesc || tx.addDescription || '',
        transactionDate: tx.transactionDate || tx.bookingDate || tx.postingDate || '',
        refNo: tx.refNo || tx.transactionId || tx.ftCode || tx.ref || '',
        accountNo: tx.accountNo || process.env.MBBANK_ACCOUNT_NUMBER || '',
        benAccountName: tx.benAccountName || tx.senderName || tx.counterpartName || '',
        senderName: tx.senderName || tx.benAccountName || tx.counterpartName || '',
    };
}

function extractTxList(raw) {
    if (!raw) return [];
    if (Array.isArray(raw)) return raw;
    if (Array.isArray(raw.transactionHistoryList)) return raw.transactionHistoryList;
    if (Array.isArray(raw.transactions)) return raw.transactions;
    if (Array.isArray(raw.data)) return raw.data;
    if (raw.data && Array.isArray(raw.data.transactionHistoryList)) return raw.data.transactionHistoryList;
    return [];
}

app.get('/health', (req, res) => {
    res.json({
        success: true,
        message: 'MBBank service is running',
        sessionActive: Boolean(mb) && !isSessionExpired(),
        accountConfigured: Boolean(process.env.MBBANK_ACCOUNT_NUMBER),
        lib: 'mbbank (CookieGMVN)',
    });
});

app.post('/api/login', authenticateApiKey, async (req, res) => {
    try {
        const result = await loginMBBank();
        res.status(result.success ? 200 : 500).json(result);
    } catch (error) {
        res.status(500).json({ success: false, message: error.message });
    }
});

app.get('/api/balance', authenticateApiKey, async (req, res) => {
    try {
        await ensureValidSession();
        const accountNumber = process.env.MBBANK_ACCOUNT_NUMBER;
        if (!accountNumber) {
            return res.status(400).json({ success: false, message: 'MBBANK_ACCOUNT_NUMBER not set' });
        }
        // getBalance may return all accounts or one account depending on version
        let balance;
        try {
            balance = await mb.getBalance(accountNumber);
        } catch {
            balance = await mb.getBalance();
        }
        // Normalize
        let available = balance?.availableBalance ?? balance?.balance;
        let accountName = balance?.accountName || process.env.MBBANK_ACCOUNT_NAME || '';
        if (Array.isArray(balance)) {
            const hit = balance.find(a => String(a.accountNumber || a.acctNo) === String(accountNumber)) || balance[0];
            available = hit?.availableBalance ?? hit?.balance ?? available;
            accountName = hit?.accountName || accountName;
        } else if (balance?.balances || balance?.accountList) {
            const list = balance.balances || balance.accountList;
            const hit = (list || []).find(a => String(a.accountNumber || a.acctNo) === String(accountNumber));
            if (hit) {
                available = hit.availableBalance ?? hit.balance;
                accountName = hit.accountName || accountName;
            }
        }
        res.json({
            success: true,
            data: {
                accountNumber,
                balance: available,
                currency: 'VND',
                accountName,
            },
        });
    } catch (error) {
        console.error('Get balance error:', error.message);
        // force re-login next time
        lastLoginAt = 0;
        res.status(500).json({ success: false, message: error.message });
    }
});

app.post('/api/transactions', authenticateApiKey, async (req, res) => {
    try {
        await ensureValidSession();
        const accountNumber = process.env.MBBANK_ACCOUNT_NUMBER;
        if (!accountNumber) {
            return res.status(400).json({ success: false, message: 'MBBANK_ACCOUNT_NUMBER not set' });
        }

        const { fromDate, toDate, days } = req.body || {};
        let startDate, endDate;
        if (days) {
            endDate = new Date();
            startDate = new Date();
            startDate.setDate(startDate.getDate() - Number(days));
        } else {
            startDate = fromDate ? new Date(fromDate) : new Date(Date.now() - 2 * 24 * 60 * 60 * 1000);
            endDate = toDate ? new Date(toDate) : new Date();
        }

        const raw = await mb.getTransactionsHistory({
            accountNumber,
            fromDate: formatDate(startDate),
            toDate: formatDate(endDate),
        });

        const transactions = extractTxList(raw).map(normalizeTx).filter(Boolean);

        res.json({
            success: true,
            data: {
                accountNumber,
                fromDate: formatDate(startDate),
                toDate: formatDate(endDate),
                transactions,
            },
        });
    } catch (error) {
        console.error('Get transactions error:', error.message);
        lastLoginAt = 0;
        res.status(500).json({ success: false, message: error.message });
    }
});

app.post('/api/check-deposits', authenticateApiKey, async (req, res) => {
    try {
        await ensureValidSession();
        const accountNumber = process.env.MBBANK_ACCOUNT_NUMBER;
        if (!accountNumber) {
            return res.status(400).json({ success: false, message: 'MBBANK_ACCOUNT_NUMBER not set' });
        }

        const { days = 2, pattern = '' } = req.body || {};
        const endDate = new Date();
        const startDate = new Date();
        startDate.setDate(startDate.getDate() - Number(days));

        const raw = await mb.getTransactionsHistory({
            accountNumber,
            fromDate: formatDate(startDate),
            toDate: formatDate(endDate),
        });

        const pat = String(pattern || '').toLowerCase();
        const deposits = extractTxList(raw)
            .map(normalizeTx)
            .filter(Boolean)
            .filter(tx => {
                if (!(tx.creditAmount > 0)) return false;
                if (!pat) return true;
                return (tx.description || '').toLowerCase().includes(pat);
            });

        res.json({
            success: true,
            data: {
                totalDeposits: deposits.length,
                deposits: deposits.map(tx => ({
                    amount: tx.creditAmount,
                    description: tx.description,
                    transactionDate: tx.transactionDate,
                    refNo: tx.refNo,
                    accountNo: tx.accountNo,
                    benAccountName: tx.benAccountName || 'Unknown',
                })),
            },
        });
    } catch (error) {
        console.error('Check deposits error:', error.message);
        lastLoginAt = 0;
        res.status(500).json({ success: false, message: error.message });
    }
});

app.use((err, req, res, next) => {
    console.error('Server error:', err);
    res.status(500).json({ success: false, message: 'Internal server error' });
});

async function startServer() {
    mb = createClient();
    if (mb) {
        await loginMBBank().catch((e) => console.warn('Boot login:', e.message || e));
    }

    app.listen(PORT, HOST, () => {
        console.log(`MBBank service on http://${HOST}:${PORT}`);
        console.log('  GET  /health');
        console.log('  POST /api/login');
        console.log('  GET  /api/balance');
        console.log('  POST /api/transactions');
        console.log('  POST /api/check-deposits');
    });
}

startServer();
