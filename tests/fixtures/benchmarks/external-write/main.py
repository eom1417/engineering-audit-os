import argparse
import settings


def main():
    argparse.ArgumentParser(prog="limits").parse_args()
    settings.LIMIT = 99
    return settings.LIMIT
