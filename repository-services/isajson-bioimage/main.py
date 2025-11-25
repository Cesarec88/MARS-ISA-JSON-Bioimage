import httpx
from fastapi import FastAPI, HTTPException

app = FastAPI()

# Configuration
BIOSTUDIES_API_URL = (
    "https://ftp.ebi.ac.uk/biostudies/fire/"  # Replace with actual source
)


@app.get("/accession/{accession_code}")
async def get_data_by_accession(accession_code: str):
    """
    Takes an accession code, queries an external service, and returns the result.
    """
    async with httpx.AsyncClient() as client:
        try:
            if "S-BIAD" not in accession_code:
                raise HTTPException(status_code=400, detail="Invalid Accession Code")
            else:
                accession_folder = "S-BIAD"
                accession_number = accession_code.strip("S-BIAD")

            # Adjust the URL structure or query parameters as required by the target API
            response = await client.get(
                f"{BIOSTUDIES_API_URL}{accession_folder}/{accession_number}/{accession_code}/{accession_code}.json"
            )

            # Raise error if external request failed
            response.raise_for_status()

            return response.json()

        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=e.response.status_code, detail=str(e))
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Internal Server Error: {str(e)}"
            )


@app.post("/isa-json/")
async def submit_isa_json(isa_json: dict):
    """
    Takes an accession code, queries an external service, and returns the result.
    """
    return isa_json


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
