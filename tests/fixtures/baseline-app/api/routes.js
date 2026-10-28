// The account routes of the new API: each checks the sign-in itself.
const express = require('express');
const router = express.Router();

router.get('/profile', (req, res) => {
  if (!req.user) return res.status(401).json({ error: 'sign in first' });
  res.json({ name: req.user.name });
});

router.get('/addresses', (req, res) => {
  if (!req.user) return res.status(401).json({ error: 'sign in first' });
  res.json(req.user.addresses || []);
});

router.post('/password', (req, res) => {
  if (!req.headers.authorization) return res.status(401).json({ error: 'sign in first' });
  res.status(204).end();
});

module.exports = router;
