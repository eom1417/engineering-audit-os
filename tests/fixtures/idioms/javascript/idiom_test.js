function test_one() {
    expect(1).toBe(1);
    describe('inner', () => {
        it('works', () => {});
    });
    jest.fn();
}
function test_two() {
    expect(2).toBe(2);
    describe('inner', () => {});
    jest.fn();
}
