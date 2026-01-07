"""
Skill model and database operations.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional
import json

from database.connection import get_db_connection, row_to_dict


@dataclass
class Skill:
    """Represents a normalized skill in the skills dictionary."""
    
    id: Optional[int] = None
    name: str = ""
    aliases: Optional[list[str]] = None  # Alternative names for this skill
    category: Optional[str] = None  # language, framework, database, cloud, tool, etc.
    parent_skill_id: Optional[int] = None  # For hierarchies (React -> JavaScript)
    created_at: Optional[datetime] = None
    
    @classmethod
    def from_row(cls, row) -> "Skill":
        """Create a Skill from a database row."""
        data = row_to_dict(row) if hasattr(row, 'keys') else dict(row)
        
        # Parse JSON aliases
        if data.get('aliases'):
            try:
                data['aliases'] = json.loads(data['aliases'])
            except (json.JSONDecodeError, TypeError):
                data['aliases'] = None
        
        return cls(**data)
    
    @classmethod
    def from_dict(cls, data: dict) -> "Skill":
        """Create a Skill from a dictionary."""
        known_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in known_fields}
        return cls(**filtered)
    
    def to_dict(self) -> dict:
        """Convert Skill to a dictionary."""
        return {
            'id': self.id,
            'name': self.name,
            'aliases': json.dumps(self.aliases) if self.aliases else None,
            'category': self.category,
            'parent_skill_id': self.parent_skill_id,
        }


# Skill aliases for normalization
SKILL_ALIASES = {
    "python": ["python3", "py", "python 3.x", "python3.x"],
    "javascript": ["js", "es6", "ecmascript", "es2015+"],
    "typescript": ["ts"],
    "kubernetes": ["k8s", "kube"],
    "postgresql": ["postgres", "psql", "pg"],
    "amazon web services": ["aws", "amazon aws"],
    "google cloud platform": ["gcp", "google cloud"],
    "microsoft azure": ["azure"],
    "machine learning": ["ml"],
    "artificial intelligence": ["ai"],
    "react": ["reactjs", "react.js"],
    "vue": ["vuejs", "vue.js"],
    "angular": ["angularjs", "angular.js"],
    "node.js": ["nodejs", "node"],
    "docker": ["containers", "containerization"],
    "ci/cd": ["cicd", "continuous integration", "continuous deployment"],
    "graphql": ["gql"],
    "rest api": ["restful", "rest apis", "restful api"],
    "sql": ["structured query language"],
    "nosql": ["no-sql", "non-relational"],
    "mongodb": ["mongo"],
    "redis": ["redis cache"],
    "elasticsearch": ["elastic", "es"],
    "terraform": ["tf"],
    "ansible": ["ansible automation"],
    "git": ["github", "gitlab", "version control"],
}


def normalize_skill_name(raw_skill: str) -> str:
    """
    Normalize a skill name to its canonical form.
    
    Args:
        raw_skill: Raw skill name from job posting.
    
    Returns:
        Canonical skill name.
    """
    lower = raw_skill.lower().strip()
    
    # Check if it matches a canonical name or any alias
    for canonical, aliases in SKILL_ALIASES.items():
        if lower == canonical or lower in aliases:
            # Return title case of canonical name
            return canonical.title()
    
    # Not found in aliases, return title case of original
    return raw_skill.strip().title()


# Database operations

def save_skill(skill: Skill) -> Skill:
    """Insert or update a skill."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        if skill.id:
            cursor.execute("""
                UPDATE skills SET
                    name = ?,
                    aliases = ?,
                    category = ?,
                    parent_skill_id = ?
                WHERE id = ?
            """, (
                skill.name,
                json.dumps(skill.aliases) if skill.aliases else None,
                skill.category,
                skill.parent_skill_id,
                skill.id,
            ))
        else:
            cursor.execute("""
                INSERT INTO skills (name, aliases, category, parent_skill_id)
                VALUES (?, ?, ?, ?)
            """, (
                skill.name,
                json.dumps(skill.aliases) if skill.aliases else None,
                skill.category,
                skill.parent_skill_id,
            ))
            skill.id = cursor.lastrowid
    
    return skill


def get_skill_by_id(skill_id: int) -> Optional[Skill]:
    """Get a skill by ID."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM skills WHERE id = ?", (skill_id,))
        row = cursor.fetchone()
        return Skill.from_row(row) if row else None


def get_skill_by_name(name: str) -> Optional[Skill]:
    """Get a skill by exact name match."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM skills WHERE name = ?", (name,))
        row = cursor.fetchone()
        return Skill.from_row(row) if row else None


def get_or_create_skill(name: str, category: Optional[str] = None) -> Skill:
    """
    Get an existing skill or create a new one.
    
    Args:
        name: Skill name (will be normalized).
        category: Optional skill category.
    
    Returns:
        Skill object (existing or newly created).
    """
    normalized_name = normalize_skill_name(name)
    
    existing = get_skill_by_name(normalized_name)
    if existing:
        return existing
    
    skill = Skill(name=normalized_name, category=category)
    return save_skill(skill)


def get_all_skills() -> list[Skill]:
    """Get all skills ordered by name."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM skills ORDER BY name")
        return [Skill.from_row(row) for row in cursor.fetchall()]


def get_skills_by_category(category: str) -> list[Skill]:
    """Get all skills in a specific category."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM skills WHERE category = ? ORDER BY name",
            (category,)
        )
        return [Skill.from_row(row) for row in cursor.fetchall()]


def search_skills(query: str) -> list[Skill]:
    """Search skills by name (case-insensitive partial match)."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM skills WHERE name LIKE ? ORDER BY name",
            (f"%{query}%",)
        )
        return [Skill.from_row(row) for row in cursor.fetchall()]


def count_skills() -> int:
    """Count total skills."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM skills")
        return cursor.fetchone()[0]
