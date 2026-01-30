"""Shared utility functions for company operations."""

from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from packages.database.src.models import Company


async def verify_company_exists(db: AsyncSession, company_id: UUID) -> Company:
    """Verify company exists and return it.

    Args:
        db: Database session
        company_id: Company UUID to verify

    Returns:
        Company model if found

    Raises:
        HTTPException: 404 if company not found
    """
    company = await db.get(Company, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    return company
