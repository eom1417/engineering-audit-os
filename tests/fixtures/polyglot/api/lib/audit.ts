export function auditLog(action: string, subject: string) {
  return { action, subject, sink: process.env.AUDIT_SINK || 'stdout' };
}
