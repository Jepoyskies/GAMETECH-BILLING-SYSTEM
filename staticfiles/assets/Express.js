// app.js
const express = require('express');
const bodyParser = require('body-parser');
const app = express();
app.use(bodyParser.json());

// Mock Data (replace with real DB in production)
let users = [ { id: 1, name: 'Alice', email: 'alice@isp.com', phone: '1234567890' } ];
let admins = [ { id: 1, name: 'Admin', email: 'admin@isp.com' } ];
let tickets = [];

// Admin creates a repair ticket for a user
app.post('/api/admin/tickets', (req, res) => {
    // In production, verify admin authentication here
    const { user_id, admin_id, subject, description } = req.body;
    const user = users.find(u => u.id === user_id);
    const admin = admins.find(a => a.id === admin_id);
    if (!user || !admin) {
        return res.status(400).json({ error: 'User or Admin not found' });
    }
    const ticket = {
        id: tickets.length + 1,
        user_id,
        admin_id,
        subject,
        description,
        status: 'open',
        created_at: new Date().toISOString()
    };
    tickets.push(ticket);
    res.status(201).json(ticket);
});

// List all tickets (optional: filter by user, status, etc.)
app.get('/api/admin/tickets', (req, res) => {
    res.json(tickets);
});

app.listen(3000, () => console.log('ISP Repair Ticket API running on port 3000'));
