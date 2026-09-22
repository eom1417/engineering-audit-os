package main

import (
    "net/http"
    "time"
)

func MakeClient() *http.Client {
    transport := &http.Transport{
        MaxIdleConns:        100,
        MaxIdleConnsPerHost: 10,
        IdleConnTimeout:     90 * time.Second,
    }
    return &http.Client{Transport: transport}
}
