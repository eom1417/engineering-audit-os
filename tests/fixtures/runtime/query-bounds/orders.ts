// TypeScript fixture for query-bound detection.
async function getMany(): Promise<Order[]> {
    return await prisma.order.findMany({});
}

async function getBounded(n: number): Promise<Order[]> {
    return await prisma.order.findMany({ take: n });
}

async function getFirst(): Promise<Order | null> {
    return await prisma.order.findFirst();
}
