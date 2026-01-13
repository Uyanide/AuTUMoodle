group "default" {
    targets = ["requests", "playwright"]
}

target "requests" {
    context = ".."
    dockerfile = "Dockerfile"
    tags = ["autumoodle:requests"]
    args = {
        SESSION_TYPE = "requests"
    }
}

target "playwright" {
    context = ".."
    dockerfile = "Dockerfile"
    tags = ["autumoodle:playwright"]
    args = {
        SESSION_TYPE = "playwright"
    }
}
