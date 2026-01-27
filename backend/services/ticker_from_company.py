from fastapi import HTTPException, status
import requests
import urllib
import json
from backend.RequestSchemas.ingestion import IngestRequest
from backend.config.config import get_settings
from backend.services.InternalSchemas.resolver import ResolverResponse
from urllib.error import HTTPError

settings = get_settings()
API_KEY = settings.OPENFIGI_API_KEY
API_BASE_URL = settings.OPENFIGI_API_BASE_URL

JsonType = None | int | str | bool | list["JsonType"] | dict[str, "JsonType"]

def _api_call(path: str, data: dict | None = None, method: str = "POST",) -> JsonType:
    """
    Make an api call to `api.openfigi.com`.
    Uses builtin `urllib` library, end users may prefer to
    swap out this function with another library of their choice

    Args:
        path (str): API endpoint, for example "search"
        method (str, optional): HTTP request method. Defaults to "POST".
        data (dict | None, optional): HTTP request data. Defaults to None.

    Returns:
        JsonType: Response of the api call parsed as a JSON object
    """

    headers = {"Content-Type": "application/json"}
    if API_KEY:
        headers |= {"X-OPENFIGI-APIKEY": API_KEY}

    request = urllib.request.Request(
        url=urllib.parse.urljoin(API_BASE_URL, path),
        data=data and bytes(json.dumps(data), encoding="utf-8"),
        headers=headers,
        method=method,
    )

    try: 
        with urllib.request.urlopen(request) as response:
            json_response_as_string = response.read().decode("utf-8")
            json_obj = json.loads(json_response_as_string)
            return json_obj
    except HTTPError as e:
        if e.code in (400, 422):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,detail="Given invalid request.") from e
        if e.code in (401, 403):
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY,detail="Resolver API key is invalid.") from e
    
def resolve_company_to_ticker(search_payload: IngestRequest):
    print("company search request:", search_payload.company_name_query)
    search_request = {
        "query": search_payload.company_name_query,
        "securityType": search_payload.security_type,
        "exchCode": search_payload.exchange_code
    }
    search_response = _api_call("/v3/search", search_request)
    data = search_response.get("data") or []
    # print(data)
    if not data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No company found for the query.")
    best_response_raw = data[0]
    best_response = ResolverResponse(
        name=best_response_raw.get('name'),
        ticker=best_response_raw.get('ticker'),
        exchCode=best_response_raw.get('exchCode'),
        securityType=best_response_raw.get('securityType'),
        marketSector=best_response_raw.get('marketSector')
    )
    
    return best_response 