import argparse
import orders


def main():
    argparse.ArgumentParser(prog='cycle-demo').parse_args()
    return orders.place({'id': 1})
