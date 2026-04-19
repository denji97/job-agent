import asyncio
import base64
import json
from typing import List

import httpx
import requests
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("server-job-listings")

HEADERS = {
    "User-Agent": "Jobsuche/2.9.2 (de.arbeitsagentur.jobboerse; build:1077; iOS 15.1.0) Alamofire/5.4.4",
    "Host": "rest.arbeitsagentur.de",
    "X-API-Key": "jobboerse-jobsuche",
    "Connection": "keep-alive",
}


@mcp.tool()
def get_job_ids(job_title: str, city: str, radius: int) -> str:
    """Queries job listings based on the 'job_title', 'city' and 'radius'.
    This function only returns the job title and reference number of the job listing. The reference number is essential to query job descriptions.
    After the function returned the job title and reference number
    a filtering of relevant jobs must be done. Once relevant jobs and their reference number are identified a list of
    reference numbers can be used as input for the tool 'get_job_descriptions'

    Args:
        job_title (str): job title of key word to search for job listings
        city (str): city in which to search for jobs
        radius (int): radius of acceptable travel distance to the office. Must be less or equal than 200.

    Returns:
        str: returns a string formatted JSON containing job titles, name of the employer and job listing reference number.
    """
    params = (
        ("angebotsart", "1"),
        ("page", "1"),
        ("pav", "false"),
        ("size", "100"),
        ("umkreis", f"{max(min(radius, 200), 0)}"),
        ("arbeitszeit", "vz"),
        ("befristung", "2"),
        ("was", job_title),
        ("wo", city),
    )
    response = requests.get(
        "https://rest.arbeitsagentur.de/jobboerse/jobsuche-service/pc/v4/jobs",
        headers=HEADERS,
        params=params,
        verify=True,
    ).json()
    jobs_str = [
        {
            "job_title": job_dict["titel"],
            "employee_name": job_dict["arbeitgeber"],
            "refnr": job_dict["refnr"],
        }
        for job_dict in response["stellenangebote"]
    ]
    return json.dumps(jobs_str, ensure_ascii=False)


@mcp.tool()
async def get_job_descriptions(ref_numbers: List[str]) -> str:
    """After the tool 'get_job_ids' was called and relevant reference
    numbers were filtered, this tool takes a list of reference numbers
    and queries the full job descriptions.

    Args:
        ref_numbers: List of reference numbers for jobs to query.

    Returns:
        str: JSON-formatted job descriptions including title,
             employer, and description text.
    """

    async def fetch_one(client: httpx.AsyncClient, ref_number: str):
        encrypted = base64.b64encode(ref_number.encode()).decode()
        response = await client.get(
            f"https://rest.arbeitsagentur.de/jobboerse/jobsuche-service/pc/v4/jobdetails/{encrypted}",
            headers=HEADERS,
        )
        data = response.json()
        return {
            "job_title": data["stellenangebotsTitel"],
            "employee_name": data["firma"],
            "description": data["stellenangebotsBeschreibung"],
        }

    async with httpx.AsyncClient(verify=True) as client:
        job_descriptions = await asyncio.gather(
            *[fetch_one(client, ref) for ref in ref_numbers]
        )
    return json.dumps(job_descriptions, ensure_ascii=False)


if __name__ == "__main__":
    mcp.run()
