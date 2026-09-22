package main

import (
    "context"
    "github.com/jackc/pgx/v4/pgxpool"
)

func MakePool(ctx context.Context, url string) (*pgxpool.Pool, error) {
    cfg, err := pgxpool.ParseConfig(url)
    if err != nil { return nil, err }
    cfg.MaxConns = 30
    cfg.MinConns = 5
    return pgxpool.NewWithConfig(ctx, cfg)
}
