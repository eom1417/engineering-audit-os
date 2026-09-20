import argparse
import store


def main():
    argparse.ArgumentParser(prog="cache").parse_args()
    return store.remember("a", 1)
