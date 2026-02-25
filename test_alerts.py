import urllib.request, json
try:
    r = urllib.request.urlopen('http://localhost:8888/api/alerts')
    data = json.load(r)
    print(f'Status: OK | {len(data)} low-stock alerts')
    for item in data:
        p = item['payload']
        print(f'  [{p["urgency"]}] {p["item_name"]} — {p["current_qty"]}/{p["threshold"]} | reorder {p["reorder_qty"]} units')
except Exception as e:
    print(f'ERROR: {e}')
