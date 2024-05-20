def custom_preprocessing_hook(endpoints):
    filtered = []
    paths = [
        '/api/v1/payment_types/',
        '/api/v1/payment/',
        '/api/v1/payment/{pk}/',
        '/api/v1/payment/{pk}/send_card_data/',
        '/api/v1/payment/{pk}/send_sms_code/',
    ]
    for (path, path_regex, method, callback) in endpoints:
        print(path)
        # if "api" in path:
        if path in paths:
            filtered.append((path, path_regex, method, callback))
    return filtered
