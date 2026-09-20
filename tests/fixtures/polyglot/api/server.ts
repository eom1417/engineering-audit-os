import express from 'express';
import { createOrder, listOrders } from './handlers/orders';
import { auditLog } from './lib/audit';

const app = express();
const PORT = process.env.PORT || 3000;

app.get('/orders', listOrders);
app.post('/orders', createOrder);

app.delete('/orders/:id', async (req, res) => {
  auditLog('delete', req.params.id);
  res.status(204).send();
});

export function start() {
  app.listen(PORT);
}
