"""Access Control for Agents and Tools.

Implements RBAC (Role-Based Access Control) with:
- Roles: Define permission bundles
- Permissions: Fine-grained access rights
- Agent Permissions: What each agent can access
- Tool Boundaries: Read vs Write vs Admin

Principle: Least privilege by default.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Permission(Enum):
    """Fine-grained permissions."""

    # Tool permissions
    TOOL_READ = "tool:read"
    TOOL_WRITE = "tool:write"
    TOOL_DELETE = "tool:delete"
    TOOL_ADMIN = "tool:admin"

    # Data permissions
    DATA_READ_PUBLIC = "data:read:public"
    DATA_READ_INTERNAL = "data:read:internal"
    DATA_READ_SENSITIVE = "data:read:sensitive"
    DATA_WRITE = "data:write"
    DATA_EXPORT = "data:export"

    # Agent permissions
    AGENT_INVOKE = "agent:invoke"
    AGENT_CONFIGURE = "agent:configure"

    # CRM permissions
    CRM_READ = "crm:read"
    CRM_WRITE = "crm:write"
    CRM_SYNC = "crm:sync"

    # Enrichment permissions
    ENRICH_COMPANY = "enrich:company"
    ENRICH_CONTACT = "enrich:contact"
    ENRICH_EMAIL = "enrich:email"

    # Scraping permissions
    SCRAPE_PUBLIC = "scrape:public"
    SCRAPE_LINKEDIN = "scrape:linkedin"

    # Communication permissions
    COMM_EMAIL_DRAFT = "comm:email:draft"
    COMM_EMAIL_SEND = "comm:email:send"
    COMM_SLACK = "comm:slack"

    # Budget permissions
    BUDGET_VIEW = "budget:view"
    BUDGET_ALLOCATE = "budget:allocate"


@dataclass
class Role:
    """A role bundles permissions."""

    id: str
    name: str
    description: str
    permissions: set[Permission]
    is_system: bool = False  # System roles can't be deleted

    def has_permission(self, permission: Permission) -> bool:
        """Check if role has a permission."""
        return permission in self.permissions

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "permissions": [p.value for p in self.permissions],
            "is_system": self.is_system,
        }


# Pre-defined system roles
ROLE_READ_ONLY = Role(
    id="read_only",
    name="Read Only",
    description="Can only read public data, no mutations",
    permissions={
        Permission.TOOL_READ,
        Permission.DATA_READ_PUBLIC,
        Permission.AGENT_INVOKE,
        Permission.BUDGET_VIEW,
    },
    is_system=True,
)

ROLE_ANALYST = Role(
    id="analyst",
    name="Analyst",
    description="Can read data and use enrichment tools",
    permissions={
        Permission.TOOL_READ,
        Permission.DATA_READ_PUBLIC,
        Permission.DATA_READ_INTERNAL,
        Permission.AGENT_INVOKE,
        Permission.CRM_READ,
        Permission.ENRICH_COMPANY,
        Permission.SCRAPE_PUBLIC,
        Permission.BUDGET_VIEW,
    },
    is_system=True,
)

ROLE_OPERATOR = Role(
    id="operator",
    name="Operator",
    description="Can read and write data, use most tools",
    permissions={
        Permission.TOOL_READ,
        Permission.TOOL_WRITE,
        Permission.DATA_READ_PUBLIC,
        Permission.DATA_READ_INTERNAL,
        Permission.DATA_WRITE,
        Permission.AGENT_INVOKE,
        Permission.CRM_READ,
        Permission.CRM_WRITE,
        Permission.ENRICH_COMPANY,
        Permission.ENRICH_CONTACT,
        Permission.SCRAPE_PUBLIC,
        Permission.COMM_EMAIL_DRAFT,
        Permission.BUDGET_VIEW,
    },
    is_system=True,
)

ROLE_ADMIN = Role(
    id="admin",
    name="Administrator",
    description="Full access to all features",
    permissions=set(Permission),  # All permissions
    is_system=True,
)


@dataclass
class AgentPermissions:
    """Permission configuration for an agent."""

    agent_id: str
    agent_name: str
    roles: list[Role] = field(default_factory=list)
    explicit_grants: set[Permission] = field(default_factory=set)
    explicit_denies: set[Permission] = field(default_factory=set)
    tool_allowlist: list[str] | None = None  # None = all tools
    tool_denylist: list[str] = field(default_factory=list)
    requires_approval_for: list[Permission] = field(default_factory=list)

    def has_permission(self, permission: Permission) -> bool:
        """Check if agent has permission (with deny taking precedence)."""
        # Explicit deny always wins
        if permission in self.explicit_denies:
            return False

        # Explicit grant
        if permission in self.explicit_grants:
            return True

        # Check roles
        for role in self.roles:
            if role.has_permission(permission):
                return True

        return False

    def can_use_tool(self, tool_name: str) -> bool:
        """Check if agent can use a specific tool."""
        # Check denylist first
        if tool_name in self.tool_denylist:
            return False

        # Check allowlist if specified
        if self.tool_allowlist is not None:
            return tool_name in self.tool_allowlist

        return True

    def needs_approval(self, permission: Permission) -> bool:
        """Check if permission requires human approval."""
        return permission in self.requires_approval_for

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "agent_name": self.agent_name,
            "roles": [r.to_dict() for r in self.roles],
            "explicit_grants": [p.value for p in self.explicit_grants],
            "explicit_denies": [p.value for p in self.explicit_denies],
            "tool_allowlist": self.tool_allowlist,
            "tool_denylist": self.tool_denylist,
            "requires_approval_for": [p.value for p in self.requires_approval_for],
        }


class AccessControl:
    """Central access control manager.

    Example:
        ac = AccessControl()

        # Define agent permissions
        ac.configure_agent(AgentPermissions(
            agent_id="lead_hunter",
            agent_name="Lead Hunter Agent",
            roles=[ROLE_ANALYST],
            explicit_grants={Permission.ENRICH_EMAIL},
            tool_allowlist=["company_enrichment", "email_finder"],
            requires_approval_for=[Permission.COMM_EMAIL_SEND],
        ))

        # Check access
        if ac.can("lead_hunter", Permission.ENRICH_COMPANY):
            # proceed
            pass
    """

    def __init__(self):
        self._roles: dict[str, Role] = {
            "read_only": ROLE_READ_ONLY,
            "analyst": ROLE_ANALYST,
            "operator": ROLE_OPERATOR,
            "admin": ROLE_ADMIN,
        }
        self._agent_permissions: dict[str, AgentPermissions] = {}
        self._access_log: list[dict[str, Any]] = []

    def add_role(self, role: Role) -> None:
        """Add a custom role."""
        self._roles[role.id] = role

    def get_role(self, role_id: str) -> Role | None:
        """Get a role by ID."""
        return self._roles.get(role_id)

    def configure_agent(self, config: AgentPermissions) -> None:
        """Configure permissions for an agent."""
        self._agent_permissions[config.agent_id] = config

    def get_agent_config(self, agent_id: str) -> AgentPermissions | None:
        """Get agent's permission configuration."""
        return self._agent_permissions.get(agent_id)

    def can(
        self,
        agent_id: str,
        permission: Permission,
        log: bool = True,
    ) -> bool:
        """Check if agent has permission."""
        config = self._agent_permissions.get(agent_id)

        if not config:
            # Unknown agents have no permissions by default
            result = False
        else:
            result = config.has_permission(permission)

        if log:
            self._access_log.append(
                {
                    "agent_id": agent_id,
                    "permission": permission.value,
                    "granted": result,
                }
            )

        return result

    def can_use_tool(self, agent_id: str, tool_name: str) -> bool:
        """Check if agent can use a tool."""
        config = self._agent_permissions.get(agent_id)
        if not config:
            return False
        return config.can_use_tool(tool_name)

    def needs_approval(self, agent_id: str, permission: Permission) -> bool:
        """Check if action requires human approval."""
        config = self._agent_permissions.get(agent_id)
        if not config:
            return True  # Unknown agents always need approval
        return config.needs_approval(permission)

    def get_access_log(self) -> list[dict[str, Any]]:
        """Get access check log."""
        return self._access_log.copy()

    def list_agents(self) -> list[dict[str, Any]]:
        """List all configured agents."""
        return [c.to_dict() for c in self._agent_permissions.values()]

    def list_roles(self) -> list[dict[str, Any]]:
        """List all roles."""
        return [r.to_dict() for r in self._roles.values()]


# Pre-configured agent permissions for GTM Advisor
def create_gtm_agent_permissions() -> dict[str, AgentPermissions]:
    """Create default permissions for GTM Advisor agents."""
    return {
        "gtm_strategist": AgentPermissions(
            agent_id="gtm_strategist",
            agent_name="GTM Strategist",
            roles=[ROLE_OPERATOR],
            explicit_grants={Permission.AGENT_INVOKE},  # Can invoke other agents
            requires_approval_for=[Permission.CRM_WRITE, Permission.COMM_EMAIL_SEND],
        ),
        "market_intelligence": AgentPermissions(
            agent_id="market_intelligence",
            agent_name="Market Intelligence Agent",
            roles=[ROLE_ANALYST],
            tool_allowlist=[
                "news_scraper",
                "web_scraper",
                "company_enrichment",
            ],
        ),
        "lead_hunter": AgentPermissions(
            agent_id="lead_hunter",
            agent_name="Lead Hunter Agent",
            roles=[ROLE_ANALYST],
            explicit_grants={Permission.ENRICH_EMAIL, Permission.ENRICH_CONTACT},
            tool_allowlist=[
                "company_enrichment",
                "contact_enrichment",
                "email_finder",
                "linkedin_scraper",
            ],
        ),
        "competitor_analyst": AgentPermissions(
            agent_id="competitor_analyst",
            agent_name="Competitor Analyst Agent",
            roles=[ROLE_ANALYST],
            tool_allowlist=[
                "web_scraper",
                "news_scraper",
                "linkedin_scraper",
            ],
        ),
        "customer_profiler": AgentPermissions(
            agent_id="customer_profiler",
            agent_name="Customer Profiler Agent",
            roles=[ROLE_ANALYST],
            explicit_grants={Permission.CRM_READ},
            tool_allowlist=[
                "hubspot",
                "pipedrive",
                "company_enrichment",
            ],
        ),
        "campaign_architect": AgentPermissions(
            agent_id="campaign_architect",
            agent_name="Campaign Architect Agent",
            roles=[ROLE_OPERATOR],
            explicit_denies={Permission.CRM_WRITE},  # Can draft but not write to CRM
            tool_allowlist=[
                "hubspot",
                "pipedrive",
            ],
            requires_approval_for=[Permission.COMM_EMAIL_SEND],
        ),
    }
