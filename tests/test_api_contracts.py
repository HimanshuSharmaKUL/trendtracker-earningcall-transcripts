


def test_invalid_input_ingest_(client):
    #company name not provided
    #year less than 2006, quarter greater than 4
    #incomplete payload
    payload = {"company_name_query": "", "year": 2000, "quarter": 5}
    response = client.post("/ingest/ingest-in", json=payload)

    assert response.status_code == 422

def test_invalid_input_ingest_(client):
    #company name not provided
    #year less than 2006, quarter greater than 4
    #incomplete payload
    payload = {"company_name_query": "", "year": 2000, "quarter": 5}
    response = client.post("/ingest/ingest-in", json=payload)

    assert response.status_code == 422


def test_search_validation(client):

    response = client.post("/search/query", json={})

    assert response.status_code == 422


def test_qna_validation(client):
    response = client.post("/qna/ask", json={})

    assert response.status_code == 422
