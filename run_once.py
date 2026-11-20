"""Run one monitoring pass from a scheduled GitHub Actions job."""
from app import check_source, init_db

if __name__ == "__main__":
    init_db()
    check_source()
