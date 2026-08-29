// Module 1: Relay Server - Twenty CRM Webhook Receiver
// Listens on port 3000 for POST payloads where stage changes to QUALIFIED
// Sends cold outreach email via Resend SDK
// Returns 200 OK immediately to prevent timeouts

require('dotenv').config();
const express = require('express');
const { Resend } = require('resend');

const app = express();
const PORT = 3000;

// Middleware for JSON parsing
app.use(express.json({ verify: (req, res, buf) => { req.rawBody = buf; } }));

// Resend SDK initialization
const resend = new Resend(process.env.RESEND_API_KEY);

// Twenty CRM webhook endpoint
app.post('/twenty-webhook', async (req, res) => {
  try {
    const payload = req.body;
    
    // Check if stage changed to QUALIFIED
    if (payload.stage === 'QUALIFIED' && payload.email && payload.firstName) {
      // Send cold outreach email via Resend
      const { data, error } = await resend.emails.send({
        from: 'Empire AI <onboarding@empire-ai.co.uk>',
        to: [payload.email],
        subject: `Congrats on qualifying, ${payload.firstName}!`,
        text: `Hi ${payload.firstName},

Congratulations on your status change to QUALIFIED with Empire AI.

We've identified revenue optimization opportunities for your business. Would you like a personalized audit?

Best,
Empire AI Team`
      });
      
      if (error) {
        console.error('Resend error:', error);
        // Still return 200 OK to Twenty, log error
        res.status(200).json({ status: 'queued', emailError: error.message });
      } else {
        console.log('Email sent via Resend:', data.message.id);
        res.status(200).json({ status: 'ok', emailId: data.message.id });
      }
    } else {
      // Not a QUALIFIED stage change, just acknowledge
      res.status(200).json({ status: 'acknowledged', stage: payload.stage });
    }
  } catch (error) {
    console.error('Webhook error:', error);
    // Return 200 OK to prevent Twenty timeouts, log error
    res.status(200).json({ status: 'error', message: error.message });
  }
});

// Health check endpoint
app.get('/health', (req, res) => {
  res.status(200).json({ status: 'ok', uptime: process.uptime() });
});

// Start server
app.listen(PORT, () => {
  console.log(`Relay Server running on port ${PORT}`);
  console.log('Listening for Twenty CRM webhooks at /twenty-webhook');
});

process.on('SIGTERM', () => {
  console.log('SIGTERM received. Shutting down gracefully...');
  server.close(() => {
    console.log('Closed out remaining connections');
    process.exit(0);
  });
});
