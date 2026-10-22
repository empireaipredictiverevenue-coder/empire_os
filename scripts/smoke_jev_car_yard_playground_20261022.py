"""Loopback-only disposable WordPress/PHP8.3 integration smoke.

Requires the explicit locally launched WordPress Playground CLI instance with
the approved mounted theme/plugin and blueprint. No authenticated actions,
visitor contact, booking creation, payment, remote access or production writes.
"""
from __future__ import annotations

from datetime import datetime,timezone
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from pathlib import Path
import json
import re
import argparse

SCHEMA="empire.jev.car_yard_wp_playground_runtime_smoke.v1"
ROOT=Path(__file__).resolve().parents[1]
OUTPUT=ROOT/"docs/commercial/JEV_CAR_YARD_PLAYGROUND_RUNTIME_SMOKE_20261022.json"
BASE="http://127.0.0.1:9478"
PAGES={
    "/":"Local service, clear information",
    "/services/":"Services",
    "/about/":"About this business",
    "/areas/":"Service areas",
    "/contact/":"Enquiry readiness",
}


def _request(path:str, method:str="GET"):
    payload=(json.dumps({
        "resource_key":"bay-1","service_code":"inspection",
        "starts_at_utc":"2026-12-20T09:00:00Z",
        "duration_minutes":60,"vehicle_id":0,
    }).encode("utf8") if method=="POST" and path.endswith("/internal/reservations")
        else b'{"title":"FICTIONAL-TEST-NO-POST-SHOULD-BE-CREATED"}'
        if method=="POST" else None)
    req=Request(BASE+path,method=method,
                headers={"User-Agent":"EmpireOS-Disposable-WordPress-Integration-Smoke/1.0",
                         "Content-Type":"application/json",
                         "Accept":"application/json,text/html"},
                data=payload)
    try:
        with urlopen(req,timeout=6) as response:
            return response.status,response.read(300000),dict(response.headers)
    except HTTPError as error:
        return error.code,error.read(200000),dict(error.headers)


def smoke()->dict:
    results={}
    for route,heading in PAGES.items():
        status,raw,headers=_request(route)
        html=raw.decode("utf8","replace")
        text=re.sub("<[^>]+>"," ",html)
        if (status!=200 or heading.lower() not in text.lower()
            or "empire-local-services" not in html):
            raise ValueError(
                "theme failed real WordPress HTML page "+route+
                " status="+str(status)+
                " heading="+str(heading.lower() in text.lower())+
                " theme="+str("empire-local-services" in html)+
                " observed_h1="+str(re.findall(r"<h1[^>]*>(.*?)</h1>",html,re.I|re.S)[:1])[:160]
            )
        if route=="/contact/" and re.search(
            r'<form\b[^>]*\bmethod\s*=\s*["\']?post',html,re.I):
            raise ValueError("live contact submission unexpectedly enabled")
        results[route]={"http":status,"expected_demo_content":True}
    status,body,_=_request("/wp-json/wp/v2/types/empire_vehicle")
    if status!=200:
        raise ValueError("private inventory type not registered in WordPress runtime")
    posttype=json.loads(body)
    if posttype.get("slug")!="empire_vehicle":
        raise ValueError("wrong inventory post type")
    denied={}
    protected=[
        ("GET","/wp-json/empire-yard/v1/internal/reservations"),
        ("POST","/wp-json/empire-yard/v1/internal/reservations"),
        ("POST","/wp-json/empire-yard/v1/internal/reservations/1/cancel"),
        ("POST","/wp-json/wp/v2/empire_vehicle"),
    ]
    for method,route in protected:
        status,body,_=_request(route,method=method)
        if status not in (401,403):
            try: err=json.loads(body).get("code")
            except (ValueError,AttributeError): err=str(body[:120])
            raise ValueError("anonymous request not denied with 401/403 " +
                             method+" "+route+" HTTP="+str(status)+" ERR="+str(err))
        denied[method+" "+route]={"http":status,"anonymous_forbidden":True}
    return {
        "schema_version":SCHEMA,
        "status":"REAL_PLAYGROUND_WORDPRESS_PHP_THEME_AND_PRIVATE_ROUTE_SMOKE_PASS",
        "smoke_at_utc":datetime.now(timezone.utc).isoformat(),
        "runtime_kind":"OFFICIAL_WORDPRESS_PLAYGROUND_CLI_EPHEMERAL_LOCALHOST",
        "runtime_wordpress_version_configured":"6.8",
        "runtime_php_version_configured":"8.3",
        "expected_local_loopback_port":9478,
        "five_wp_page_renderings":results,
        "private_vehicle_cpt_registered":True,
        "unauthed_private_write_and_booking_routes_rejected":denied,
        "public_person_data_collection_enabled":False,
        "anonymous_booking_created":0,
        "mysql_innodb_booking_transactions_tested":False,
        "wordpress_site_editor_authenticated_workflow_tested":False,
        "wordpress_vehicle_admin_crud_tested":False,
        "wordpress_staff_internal_booking_tested":False,
        "site_mobile_browser_rendering_tested":False,
        "wordpress_email_transport_and_consent_tested":False,
        "customer_site_handover_accepted":False,
        "production_changes":False,
        "customer_messages_or_site_bids_sent":0,
        "execution_authority":"none",
    }


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--probe-loopback-only",action="store_true",required=True)
    parser.parse_args()
    if OUTPUT.exists() or OUTPUT.is_symlink():
        raise ValueError("runtime evidence packet exists; will not overwrite")
    result=smoke()
    with OUTPUT.open("x",encoding="utf8") as f:
        json.dump(result,f,sort_keys=True,indent=2)
        f.write("\n")
    print(json.dumps({
        "status":result["status"],
        "rendered_pages":len(result["five_wp_page_renderings"]),
        "denied_unauthenticated_endpoints":len(result["unauthed_private_write_and_booking_routes_rejected"]),
        "vehicle_cpt_registered":result["private_vehicle_cpt_registered"],
        "mysql_innodb_tested":result["mysql_innodb_booking_transactions_tested"],
    },sort_keys=True))


if __name__=="__main__":
    main()
