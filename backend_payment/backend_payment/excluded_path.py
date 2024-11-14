def custom_preprocessing_hook(endpoints):
    filtered = []
    paths = [
        '/api/v1/payments_archive/',
        '/api/v1/payment_types/',
        '/api/v1/payment/',
        '/api/v1/payment/{pk}/',
        '/api/v1/payment/{pk}/send_card_data/',
        '/api/v1/payment/{pk}/send_sms_code/',
        '/api/v1/payment/{pk}/send_phone/',
        '/api/v1/withdraw/',
        '/api/v1/withdraw/{pk}/',
        '/api/v1/balance_changes/'
    ]
    for (path, path_regex, method, callback) in endpoints:
        if "token" in path:
            filtered.append((path, path_regex, method, callback))
        if path in paths:
            filtered.append((path, path_regex, method, callback))
    return filtered
