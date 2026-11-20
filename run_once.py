"""Run one monitoring pass from a scheduled GitHub Actions job."""
from app import check_source

if __name__ == "__main__":
    check_source()
