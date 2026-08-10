"""Repository Registry router."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Repository, User
from ..schemas import RepositoryCreate, RepositoryUpdate, RepositoryResponse
from ..services import get_current_user
from ..services.github_integration import parse_github_identifier, sync_repository_from_github

router = APIRouter()


@router.get("", response_model=list[RepositoryResponse])
def list_repositories(
    status: str | None = None,
    provider: str | None = None,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> list[Repository]:
    q = db.query(Repository)
    if status:
        q = q.filter(Repository.status == status)
    if provider:
        q = q.filter(Repository.provider == provider)
    return q.order_by(Repository.created_at.desc()).offset(offset).limit(limit).all()


@router.post("", response_model=RepositoryResponse, status_code=201)
def create_repository(
    body: RepositoryCreate,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> Repository:
    provider = body.provider
    identifier = body.identifier
    if provider == "github" and not identifier:
        identifier = parse_github_identifier(body.url)

    repo = Repository(
        name=body.name,
        url=body.url,
        default_branch=body.default_branch,
        language=body.language,
        provider=provider,
        identifier=identifier,
    )
    db.add(repo)
    db.commit()
    db.refresh(repo)
    return repo


@router.get("/{repo_id}", response_model=RepositoryResponse)
def get_repository(
    repo_id: str,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> Repository:
    repo = db.query(Repository).filter(Repository.id == repo_id).first()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    return repo


@router.patch("/{repo_id}", response_model=RepositoryResponse)
def update_repository(
    repo_id: str,
    body: RepositoryUpdate,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> Repository:
    repo = db.query(Repository).filter(Repository.id == repo_id).first()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(repo, field, value)
    db.commit()
    db.refresh(repo)
    return repo


@router.delete("/{repo_id}", status_code=204)
def delete_repository(
    repo_id: str,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> None:
    repo = db.query(Repository).filter(Repository.id == repo_id).first()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    db.delete(repo)
    db.commit()


@router.post("/{repo_id}/sync", response_model=RepositoryResponse)
def sync_repository(
    repo_id: str,
    ref: str | None = None,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> Repository:
    repo = db.query(Repository).filter(Repository.id == repo_id).first()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    if repo.provider != "github":
        raise HTTPException(status_code=400, detail="Only GitHub repositories can be synced")
    try:
        repo = sync_repository_from_github(db, repo, ref=ref)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"GitHub sync failed: {e}")
    return repo
