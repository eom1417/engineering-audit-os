package tests

func HandlerA(req string) error {
    validate(req)
    save(req)
    notify(req)
    return nil
}

func HandlerB(req string) error {
    validate(req)
    save(req)
    notify(req)
    return nil
}

func HandlerC(req string) error {
    validate(req)
    save(req)
    notify(req)
    return nil
}
