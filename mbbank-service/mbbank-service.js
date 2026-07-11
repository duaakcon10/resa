require('dotenv').config();
const express = require('express');
const cors = require('cors');
const MBBank = require('@doa69/mbbank');

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

let mbbank = null;
let sessionData = null;
let lastLoginAt = 0;

async function initializeMBBank() {
    try {
        if (!process.env.MBBANK_USERNAME || !process.env.MBBANK_PASSWORD) {
            console.warn('MBBank credentials missing (MBBANK_USERNAME / MBBANK_PASSWORD)');
            return false;
        }
        mbbank = new MBBank({
            username: process.env.MBBANK_USERNAME,
            password: process.env.MBBANK_PASSWORD,
        });
        console.log('MBBank instance created');
        return true;
    } catch (error) {
        console.error('Failed to initialize MBBank:', error.message);
        return false;
    }
}

async function loginMBBank() {
    try {
        if (!mbbank) {
            const ok = await initializeMBBank();
            if (!ok) return { success: false, message: 'Init failed' };
        }
        sessionData = await mbbank.login();
        lastLoginAt = Date.now();
        if (sessionData && typeof sessionData === 'object') {
            sessionData.timestamp = lastLoginAt;
        }
        console.log('MBBank login successful');
        return { success: true, message: 'Login successful', data: sessionData };
    } catch (error) {
        console.error('MBBank login failed:', error.message);
        return { success: false, message: error.message };
    }
}

function isSessionExpired() {
    if (!lastLoginAt) return true;
    const SESSION_DURATION = 8 * 60 * 1000;
    return Date.now() - lastLoginAt > SESSION_DURATION;
}

async function ensureValidSession() {
    if (!sessionData || isSessionExpired()) {
        console.log('Session expired or missing, logging in...');
        await loginMBBank();
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
    const credit = Number(tx.creditAmount ?? tx.amount ?? 0) || 0;
    return {
        creditAmount: credit,
        amount: credit,
        description: tx.description || tx.transactionDesc || '',
        transactionDate: tx.transactionDate || tx.bookingDate || '',
        refNo: tx.refNo || tx.transactionId || tx.ftCode || '',
        accountNo: tx.accountNo || process.env.MBBANK_ACCOUNT_NUMBER || '',
        benAccountName: tx.benAccountName || tx.senderName || '',
        senderName: tx.senderName || tx.benAccountName || '',
    };
}

app.get('/health', (req, res) => {
    res.json({
        success: true,
        message: 'MBBank service is running',
        sessionActive: sessionData !== null && !isSessionExpired(),
        accountConfigured: Boolean(process.env.MBBANK_ACCOUNT_NUMBER),
    });
});

app.post('/api/login', authenticateApiKey, async (req, res) => {
    try {
        const result = await loginMBBank();
        res.json(result);
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
        const balance = await mbbank.getBalance(accountNumber);
        res.json({
            success: true,
            data: {
                accountNumber,
                balance: balance?.availableBalance ?? balance?.balance,
                currency: balance?.currency || 'VND',
                accountName: balance?.accountName || process.env.MBBANK_ACCOUNT_NAME || '',
            },
        });
    } catch (error) {
        console.error('Get balance error:', error.message);
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

        const raw = await mbbank.getTransactionHistory({
            accountNumber,
            fromDate: formatDate(startDate),
            toDate: formatDate(endDate),
        });

        const list = Array.isArray(raw) ? raw : (raw?.transactionHistoryList || raw?.transactions || []);
        const transactions = list.map(normalizeTx).filter(Boolean);

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

        const raw = await mbbank.getTransactionHistory({
            accountNumber,
            fromDate: formatDate(startDate),
            toDate: formatDate(endDate),
        });

        const list = Array.isArray(raw) ? raw : (raw?.transactionHistoryList || raw?.transactions || []);
        const pat = String(pattern || '').toLowerCase();

        const deposits = list
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
        res.status(500).json({ success: false, message: error.message });
    }
});

app.use((err, req, res, next) => {
    console.error('Server error:', err);
    res.status(500).json({ success: false, message: 'Internal server error' });
});

async function startServer() {
    await initializeMBBank();
    // Best-effort login on boot
    if (process.env.MBBANK_USERNAME && process.env.MBBANK_PASSWORD) {
        await loginMBBank().catch(() => {});
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
