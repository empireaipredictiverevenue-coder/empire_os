import json, urllib.request
HUB = "http://127.0.0.1:8081"

def post(path, body):
    req = urllib.request.Request(HUB + path, data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    try:
        r = urllib.request.urlopen(req, timeout=15)
        return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:300]

# 1. apply as a real buyer
print("=== 1. buyer apply ===")
st, resp = post("/v1/buyers/apply", {
    "name": "Test Roofing Co", "niche": "roofing", "metro": "DFW",
    "tier": "bronze", "email": "test@example.com", "phone": "2145550100"
})
print(st, resp)

# 2. check lanes occupied after apply
import sqlite3
c = sqlite3.connect("/root/empire_os/empire_os.db")
occ = c.execute("SELECT COUNT(*) FROM lanes WHERE occupied_by IS NOT NULL AND occupied_by != ''").fetchone()[0]
print("lanes occupied after apply:", occ)
