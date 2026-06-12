from pathlib import Path

from fastapi import APIRouter, HTTPException

from ..models import Project
from .deps import SessionDep

router = APIRouter(prefix="/api/projects/{project_id}/wiki", tags=["wiki"])


async def _wiki_root(session, project_id: str) -> Path:
    project = await session.get(Project, project_id)
    if not project or not project.host_dir:
        raise HTTPException(404, "project has no workspace yet")
    root = Path(project.host_dir) / "repo" / ".wiki"
    if not root.is_dir():
        raise HTTPException(404, "wiki not initialized")
    return root


def _tree(directory: Path, root: Path) -> list[dict]:
    entries = []
    for path in sorted(directory.iterdir(), key=lambda p: (p.is_file(), p.name)):
        if path.name.startswith("."):
            continue
        rel = str(path.relative_to(root))
        if path.is_dir():
            entries.append(
                {"path": rel, "name": path.name, "type": "dir", "children": _tree(path, root)}
            )
        elif path.suffix == ".md":
            entries.append({"path": rel, "name": path.name, "type": "file"})
    return entries


@router.get("/tree")
async def wiki_tree(project_id: str, session: SessionDep):
    root = await _wiki_root(session, project_id)
    return {"tree": _tree(root, root)}


@router.get("/page")
async def wiki_page(project_id: str, path: str, session: SessionDep):
    root = await _wiki_root(session, project_id)
    target = (root / path).resolve()
    if not str(target).startswith(str(root.resolve())) or not target.is_file():
        raise HTTPException(404, "page not found")
    return {"path": path, "content": target.read_text(errors="replace")}
