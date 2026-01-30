"""Mailgun MCP Server - Email sending and engagement tracking.

Provides evidence-backed facts from Mailgun:
- Email delivery status
- Open and click tracking
- Bounce and complaint management
- Email validation

API Documentation: https://documentation.mailgun.com/
"""

from __future__ import annotations

import base64
import os
from datetime import datetime
from typing import Any

import httpx
import structlog

from packages.mcp.src.base import APIBasedMCPServer
from packages.mcp.src.types import (
    FactType,
    MCPQueryResult,
    MCPServerConfig,
    SourceType,
)

logger = structlog.get_logger()


class MailgunMCPServer(APIBasedMCPServer):
    """MCP Server for Mailgun email service.

    Connects to Mailgun's API to:
    - Send emails (plain text, HTML, templates)
    - Track email events (opens, clicks, bounces)
    - Validate email addresses
    - Get delivery statistics

    Requires:
        - MAILGUN_API_KEY: API key from Mailgun
        - MAILGUN_DOMAIN: Sending domain (e.g., mg.yourdomain.com)

    Example:
        server = MailgunMCPServer.from_env()
        message_id = await server.send_email(
            to="recipient@example.com",
            subject="Hello",
            body="Test message"
        )
        events = await server.get_events(message_id)
    """

    BASE_URL = "https://api.mailgun.net/v3"

    def __init__(self, config: MCPServerConfig, domain: str) -> None:
        """Initialize Mailgun server.

        Args:
            config: Server configuration with API key
            domain: Mailgun sending domain
        """
        super().__init__(config)
        self._domain = domain

        # Mailgun uses HTTP Basic Auth with "api" as username
        auth_string = f"api:{config.api_key}"
        auth_bytes = base64.b64encode(auth_string.encode()).decode()

        self._client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            headers={
                "Authorization": f"Basic {auth_bytes}",
            },
            timeout=config.timeout_seconds,
        )

    @classmethod
    def from_env(cls) -> MailgunMCPServer:
        """Create server from environment variables."""
        api_key = os.getenv("MAILGUN_API_KEY")
        domain = os.getenv("MAILGUN_DOMAIN", "")

        config = MCPServerConfig(
            name="Mailgun Email",
            source_type=SourceType.MAILGUN,
            description="Mailgun email sending and tracking",
            api_key=api_key,
            requires_api_key=True,
            rate_limit_per_hour=1000,
            rate_limit_per_day=10000,
            cache_ttl_seconds=300,  # 5 minutes for events
        )
        return cls(config, domain)

    @property
    def is_configured(self) -> bool:
        """Check if API key and domain are configured."""
        return bool(self._config.api_key and self._domain)

    async def _health_check_impl(self) -> bool:
        """Verify Mailgun API accessibility."""
        try:
            response = await self._client.get(f"/{self._domain}")
            return response.status_code == 200
        except Exception as e:
            self._logger.warning("mailgun_health_check_failed", error=str(e))
            return False

    async def search(self, query: str, **kwargs: Any) -> MCPQueryResult:
        """Search email events by recipient or message ID.

        Args:
            query: Recipient email address or message ID
            **kwargs:
                - event_type: Filter by event type (delivered, opened, clicked, etc.)
                - limit: Max results (default: 50)
                - begin: Start date (ISO format)
                - end: End date (ISO format)

        Returns:
            Query result with email engagement facts
        """
        event_type = kwargs.get("event_type")
        limit = min(kwargs.get("limit", 50), 300)
        begin = kwargs.get("begin")
        end = kwargs.get("end")

        # Check cache
        cache_key = f"mailgun:events:{query}:{event_type}:{limit}"
        cached = self._get_cached(cache_key)
        if cached:
            return cached

        try:
            params: dict[str, Any] = {
                "limit": limit,
            }

            # Determine if query is email or message ID
            if "@" in query:
                params["recipient"] = query
            else:
                params["message-id"] = query

            if event_type:
                params["event"] = event_type
            if begin:
                params["begin"] = begin
            if end:
                params["end"] = end

            response = await self._client.get(
                f"/{self._domain}/events",
                params=params,
            )

            if response.status_code != 200:
                raise Exception(f"Mailgun API error {response.status_code}")

            data = response.json()
            facts = []

            for item in data.get("items", [])[:limit]:
                event_facts = self._parse_event(item)
                facts.extend(event_facts)

            result = MCPQueryResult(
                facts=facts,
                query=query,
                mcp_server=self.name,
                total_results=len(facts),
            )

            if facts:
                self._set_cached(cache_key, result)

            self._logger.info(
                "mailgun_events_retrieved",
                query=query,
                events_found=len(facts),
            )
            return result

        except Exception as e:
            self._logger.error("mailgun_search_failed", query=query, error=str(e))
            return MCPQueryResult(
                facts=[],
                query=query,
                mcp_server=self.name,
                errors=[f"Mailgun search failed: {str(e)}"],
            )

    def _parse_event(self, event: dict) -> list:
        """Convert Mailgun event to EvidencedFacts."""
        facts = []

        event_type = event.get("event", "")
        recipient = event.get("recipient", "")
        timestamp = event.get("timestamp")
        message_id = event.get("message", {}).get("headers", {}).get("message-id", "")

        # Convert timestamp
        event_time = None
        if timestamp:
            try:
                event_time = datetime.fromtimestamp(float(timestamp))
            except (ValueError, TypeError):
                pass

        # Map Mailgun events to fact types
        fact_type_map = {
            "accepted": FactType.EMAIL_SENT,
            "delivered": FactType.EMAIL_SENT,
            "opened": FactType.EMAIL_OPENED,
            "clicked": FactType.EMAIL_CLICKED,
            "failed": FactType.EMAIL_BOUNCED,
            "rejected": FactType.EMAIL_BOUNCED,
            "complained": FactType.EMAIL_BOUNCED,
            "unsubscribed": FactType.EMAIL_BOUNCED,
        }

        fact_type = fact_type_map.get(event_type, FactType.EMAIL_SENT)

        # Build claim based on event type
        if event_type == "accepted":
            claim = f"Email to {recipient} was accepted for delivery"
        elif event_type == "delivered":
            claim = f"Email was delivered to {recipient}"
        elif event_type == "opened":
            claim = f"{recipient} opened the email"
            # Add device info if available
            client_info = event.get("client-info", {})
            if client_info.get("client-type"):
                claim += f" on {client_info.get('client-type')}"
        elif event_type == "clicked":
            url = event.get("url", "a link")
            claim = f"{recipient} clicked {url}"
        elif event_type == "failed":
            reason = event.get("delivery-status", {}).get("message", "unknown reason")
            claim = f"Email to {recipient} failed: {reason}"
        elif event_type == "complained":
            claim = f"{recipient} marked the email as spam"
        elif event_type == "unsubscribed":
            claim = f"{recipient} unsubscribed"
        else:
            claim = f"Email event '{event_type}' for {recipient}"

        extracted_data = {
            "message_id": message_id,
            "recipient": recipient,
            "event_type": event_type,
            "timestamp": timestamp,
            "ip": event.get("ip"),
            "country": event.get("geolocation", {}).get("country"),
            "city": event.get("geolocation", {}).get("city"),
            "device_type": event.get("client-info", {}).get("device-type"),
            "client_type": event.get("client-info", {}).get("client-type"),
            "client_os": event.get("client-info", {}).get("client-os"),
            "url": event.get("url"),  # For click events
            "delivery_status": event.get("delivery-status", {}).get("code"),
            "delivery_message": event.get("delivery-status", {}).get("message"),
        }

        # Confidence varies by event type
        confidence_map = {
            "delivered": 0.99,  # Server confirmed delivery
            "opened": 0.90,  # Pixel tracking, can be blocked
            "clicked": 0.99,  # Confirmed action
            "failed": 0.99,  # Server confirmed failure
            "accepted": 0.95,  # In queue but not yet delivered
        }

        facts.append(
            self.create_fact(
                claim=claim,
                fact_type=fact_type.value,
                source_name="Mailgun",
                source_url=f"https://app.mailgun.com/app/sending/domains/{self._domain}/logs",
                published_at=event_time,
                confidence=confidence_map.get(event_type, 0.85),
                extracted_data=extracted_data,
                related_entities=[recipient],
            )
        )

        return facts

    async def send_email(
        self,
        to: str | list[str],
        subject: str,
        body: str,
        from_email: str | None = None,
        html: str | None = None,
        tags: list[str] | None = None,
        tracking: bool = True,
        variables: dict[str, str] | None = None,
    ) -> str | None:
        """Send an email via Mailgun.

        Args:
            to: Recipient email(s)
            subject: Email subject
            body: Plain text body
            from_email: Sender email (defaults to postmaster@domain)
            html: HTML body (optional)
            tags: Tags for tracking/filtering
            tracking: Enable open/click tracking
            variables: Custom variables for templates

        Returns:
            Message ID if successful, None otherwise
        """
        try:
            if isinstance(to, list):
                to_str = ", ".join(to)
            else:
                to_str = to

            if not from_email:
                from_email = f"postmaster@{self._domain}"

            data: dict[str, Any] = {
                "from": from_email,
                "to": to_str,
                "subject": subject,
                "text": body,
            }

            if html:
                data["html"] = html

            if tags:
                data["o:tag"] = tags

            if tracking:
                data["o:tracking"] = "yes"
                data["o:tracking-clicks"] = "yes"
                data["o:tracking-opens"] = "yes"

            if variables:
                for key, value in variables.items():
                    data[f"v:{key}"] = value

            response = await self._client.post(
                f"/{self._domain}/messages",
                data=data,
            )

            if response.status_code == 200:
                result = response.json()
                message_id = result.get("id", "").strip("<>")
                self._logger.info(
                    "mailgun_email_sent",
                    to=to_str,
                    message_id=message_id,
                )
                return message_id
            else:
                self._logger.warning(
                    "mailgun_send_failed",
                    status=response.status_code,
                    response=response.text[:200],
                )
                return None

        except Exception as e:
            self._logger.error("mailgun_send_error", error=str(e))
            return None

    async def send_template(
        self,
        to: str | list[str],
        template_name: str,
        variables: dict[str, Any],
        from_email: str | None = None,
        subject: str | None = None,
        tags: list[str] | None = None,
    ) -> str | None:
        """Send an email using a Mailgun template.

        Args:
            to: Recipient email(s)
            template_name: Name of the Mailgun template
            variables: Template variables
            from_email: Sender email
            subject: Subject line (can be in template)
            tags: Tags for tracking

        Returns:
            Message ID if successful, None otherwise
        """
        try:
            if isinstance(to, list):
                to_str = ", ".join(to)
            else:
                to_str = to

            if not from_email:
                from_email = f"postmaster@{self._domain}"

            data: dict[str, Any] = {
                "from": from_email,
                "to": to_str,
                "template": template_name,
                "o:tracking": "yes",
                "o:tracking-clicks": "yes",
                "o:tracking-opens": "yes",
            }

            if subject:
                data["subject"] = subject

            if tags:
                data["o:tag"] = tags

            # Add template variables
            for key, value in variables.items():
                data[f"v:{key}"] = str(value)

            response = await self._client.post(
                f"/{self._domain}/messages",
                data=data,
            )

            if response.status_code == 200:
                result = response.json()
                message_id = result.get("id", "").strip("<>")
                self._logger.info(
                    "mailgun_template_sent",
                    template=template_name,
                    to=to_str,
                    message_id=message_id,
                )
                return message_id
            else:
                self._logger.warning(
                    "mailgun_template_send_failed",
                    status=response.status_code,
                )
                return None

        except Exception as e:
            self._logger.error("mailgun_template_send_error", error=str(e))
            return None

    async def get_events(
        self,
        message_id: str | None = None,
        recipient: str | None = None,
        event_type: str | None = None,
        limit: int = 50,
    ) -> MCPQueryResult:
        """Get email events for a message or recipient.

        Args:
            message_id: Filter by message ID
            recipient: Filter by recipient email
            event_type: Filter by event type (delivered, opened, clicked, etc.)
            limit: Max results

        Returns:
            Query result with email engagement facts
        """
        query = message_id or recipient or ""
        return await self.search(
            query,
            event_type=event_type,
            limit=limit,
        )

    async def get_campaign_stats(self, tag: str, days: int = 7) -> MCPQueryResult:
        """Get aggregate stats for emails with a specific tag.

        Args:
            tag: Tag to filter by
            days: Number of days to look back

        Returns:
            Query result with campaign statistics
        """
        try:
            response = await self._client.get(
                f"/{self._domain}/stats/total",
                params={
                    "event": ["accepted", "delivered", "opened", "clicked", "failed"],
                    "duration": f"{days}d",
                    "tag": tag,
                },
            )

            if response.status_code != 200:
                raise Exception(f"Mailgun API error {response.status_code}")

            data = response.json()
            stats = data.get("stats", [{}])[0] if data.get("stats") else {}

            facts = []

            # Create summary fact
            total_sent = stats.get("accepted", {}).get("total", 0)
            total_delivered = stats.get("delivered", {}).get("total", 0)
            total_opened = stats.get("opened", {}).get("total", 0)
            total_clicked = stats.get("clicked", {}).get("total", 0)
            total_failed = stats.get("failed", {}).get("total", 0)

            open_rate = (total_opened / total_delivered * 100) if total_delivered > 0 else 0
            click_rate = (total_clicked / total_delivered * 100) if total_delivered > 0 else 0

            facts.append(
                self.create_fact(
                    claim=f"Campaign '{tag}' sent {total_sent} emails with {open_rate:.1f}% open rate and {click_rate:.1f}% click rate",
                    fact_type=FactType.CRM_ACTIVITY.value,
                    source_name="Mailgun",
                    source_url=f"https://app.mailgun.com/app/sending/domains/{self._domain}/stats",
                    confidence=0.99,
                    extracted_data={
                        "tag": tag,
                        "days": days,
                        "total_sent": total_sent,
                        "total_delivered": total_delivered,
                        "total_opened": total_opened,
                        "total_clicked": total_clicked,
                        "total_failed": total_failed,
                        "open_rate": round(open_rate, 2),
                        "click_rate": round(click_rate, 2),
                        "delivery_rate": round((total_delivered / total_sent * 100) if total_sent > 0 else 0, 2),
                    },
                )
            )

            return MCPQueryResult(
                facts=facts,
                query=f"campaign:{tag}",
                mcp_server=self.name,
                total_results=1,
            )

        except Exception as e:
            self._logger.error("mailgun_stats_failed", tag=tag, error=str(e))
            return MCPQueryResult(
                facts=[],
                query=f"campaign:{tag}",
                mcp_server=self.name,
                errors=[str(e)],
            )

    async def validate_email(self, email: str) -> dict[str, Any]:
        """Validate an email address using Mailgun's validation service.

        Note: This requires a Mailgun validation API key (separate from sending).

        Args:
            email: Email address to validate

        Returns:
            Validation result with is_valid, risk level, etc.
        """
        try:
            # Validation uses a different base URL
            response = await self._client.get(
                "https://api.mailgun.net/v4/address/validate",
                params={"address": email},
            )

            if response.status_code == 200:
                data = response.json()
                return {
                    "email": email,
                    "is_valid": data.get("result") == "deliverable",
                    "result": data.get("result"),
                    "risk": data.get("risk"),
                    "is_disposable": data.get("is_disposable_address", False),
                    "is_role_address": data.get("is_role_address", False),
                    "reason": data.get("reason"),
                }
            else:
                return {
                    "email": email,
                    "is_valid": None,
                    "error": f"Validation failed: {response.status_code}",
                }

        except Exception as e:
            self._logger.error("mailgun_validation_failed", email=email, error=str(e))
            return {
                "email": email,
                "is_valid": None,
                "error": str(e),
            }

    async def close(self) -> None:
        """Close HTTP client."""
        await self._client.aclose()
