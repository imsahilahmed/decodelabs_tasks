def process_data(data):
    result = []
    for item in data:
        if item.active:
            result.append(transform(item))
    return result
