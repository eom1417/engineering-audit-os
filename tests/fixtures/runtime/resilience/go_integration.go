package main

import (
    "net/http"
    "time"
)

func Protected(client *http.Client) error {
    client.Timeout = 30 * time.Second
    _, err := client.Get("https://api.example.com")
    return err
}

func Bare(client *http.Client) error {
    _, err := client.Get("https://api.example.com")
    return err
}
