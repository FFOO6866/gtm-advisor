"""SendGrid MCP Server - Email sending and analytics.

Provides evidence-backed facts from SendGrid:
- Email delivery status
- Campaign statistics
- Bounce and block management

API Documentation: https://docs.sendgrid.com/api-reference
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta
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


class SendGridMCPServer(APIBasedMCPServer):
    """MCP Server for SendGrid email service.

    Connects to SendGrid's API to:
    - Send emails (plain text, HTML, templates)
    - Get delivery statistics
    - Track campaign performance

    Requires: SENDGRID_API_KEY environment variable

    Example:
        server = SendGridMCPServer.from_env()
        message_id = await server.send_email(
            to="recipient@example.com",
            subject="Hello",
            body="Test message"
        )
    """

    BASE_URL = "https://api.sendgrid.com/v3"

    def __init__(self, config: MCPServerConfig) -> None:
        """Initialize SendGrid server.

        Args:
            config: Server configuration with API key
        """
        super().__init__(config)
        self._client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            headers={
                "Authorization": f"Bearer {config.api_key}",
                "Content-Type": "application/json",
            },
            timeout=config.timeout_seconds,
        )

    @classmethod
    def from_env(cls) -> SendGridMCPServer:
        """Create server from SENDGRID_API_KEY environment variable."""
        api_key = os.getenv("SENDGRID_API_KEY")

        config = MCPServerConfig(
            name="SendGrid Email",
            source_type=SourceType.SENDGRID,
            description="SendGrid email sending and analytics",
            api_key=api_key,
            requires_api_key=True,
            rate_limit_per_hour=1000,
            rate_limit_per_day=10000,
            cache_ttl_seconds=300,
        )
        return cls(config)

    @property
    def is_configured(self) -> bool:
        """Check if API key is configured."""
        return bool(self._config.api_key)

    async def _health_check_impl(self) -> bool:
        """Verify SendGrid API accessibility."""
        try:
            response = await self._client.get("/user/profile")
            return response.status_code == 200
        except Exception as e:
            self._logger.warning("sendgrid_health_check_failed", error=str(e))
            return False

    async def search(self, query: str, **kwargs: Any) -> MCPQueryResult:
        """Search email activity by recipient.

        Args:
            query: Recipient email address
            **kwargs:
                - limit: Max results (default: 50)

        Returns:
            Query result with email activity facts
        """
        limit = min(kwargs.get("limit", 50), 1000)

        # Check cache
        cache_key = f"sendgrid:activity:{query}:{limit}"
        cached = self._get_cached(cache_key)
        if cached:
            return cached

        try:
            # SendGrid's Email Activity API requires a specific query format
            params = {
                "limit": limit,
                "query": f'to_email="{query}"',
            }

            response = await self._client.get(
                "/messages",
                params=params,
            )

            if response.status_code != 200:
                # Activity API may not be available on all plans
                self._logger.warning(
                    "sendgrid_activity_unavailable",
                    status=response.status_code,
                )
                return MCPQueryResult(
                    facts=[],
                    query=query,
                    mcp_server=self.name,
                    warnings=["Email Activity API may require a higher plan"],
                )

            data = response.json()
            facts = []

            for message in data.get("messages", [])[:limit]:
                message_facts = self._parse_message(message)
                facts.extend(message_facts)

            result = MCPQueryResult(
                facts=facts,
                query=query,
                mcp_server=self.name,
                total_results=len(facts),
            )

            if facts:
                self._set_cached(cache_key, result)

            return result

        except Exception as e:
            self._logger.error("sendgrid_search_failed", query=query, error=str(e))
            return MCPQueryResult(
                facts=[],
                query=query,
                mcp_server=self.name,
                errors=[f"SendGrid search failed: {str(e)}"],
            )

    def _parse_message(self, message: dict) -> list:
        """Convert SendGrid message to EvidencedFacts."""
        facts = []

        msg_id = message.get("msg_id", "")
        to_email = message.get("to_email", "")
        subject = message.get("subject", "")
        status = message.get("status", "")
        last_event_time = message.get("last_event_time")

        # Parse timestamp
        event_time = None
        if last_event_time:
            try:
                event_time = datetime.fromisoformat(last_event_time.replace("Z", "+00:00"))
            except (ValueError, TypeError):
                pass

        # Map status to fact type
        status_map = {
            "delivered": FactType.EMAIL_SENT,
            "processed": FactType.EMAIL_SENT,
            "opened": FactType.EMAIL_OPENED,
            "clicked": FactType.EMAIL_CLICKED,
            "bounce": FactType.EMAIL_BOUNCED,
            "dropped": FactType.EMAIL_BOUNCED,
            "blocked": FactType.EMAIL_BOUNCED,
            "spam_report": FactType.EMAIL_BOUNCED,
        }

        fact_type = status_map.get(status, FactType.EMAIL_SENT)

        # Build claim
        if status == "delivered":
            claim = f"Email '{subject}' was delivered to {to_email}"
        elif status == "opened":
            claim = f"{to_email} opened email '{subject}'"
        elif status == "clicked":
            claim = f"{to_email} clicked a link in email '{subject}'"
        elif status in ["bounce", "dropped", "blocked"]:
            claim = f"Email to {to_email} failed ({status})"
        else:
            claim = f"Email to {to_email} status: {status}"

        extracted_data = {
            "message_id": msg_id,
            "to_email": to_email,
            "subject": subject,
            "status": status,
            "opens_count": message.get("opens_count", 0),
            "clicks_count": message.get("clicks_count", 0),
        }

        facts.append(
            self.create_fact(
                claim=claim,
                fact_type=fact_type.value,
                source_name="SendGrid",
                source_url="https://app.sendgrid.com/email_activity",
                published_at=event_time,
                confidence=0.95,
                extracted_data=extracted_data,
                related_entities=[to_email],
            )
        )

        return facts

    async def send_email(
        self,
        to: str | list[str],
        subject: str,
        body: str,
        from_email: str | None = None,
        from_name: str | None = None,
        html: str | None = None,
        categories: list[str] | None = None,
        custom_args: dict[str, str] | None = None,
    ) -> str | None:
        """Send an email via SendGrid.

        Args:
            to: Recipient email(s)
            subject: Email subject
            body: Plain text body
            from_email: Sender email
            from_name: Sender name
            html: HTML body (optional)
            categories: Categories for analytics
            custom_args: Custom arguments for webhooks

        Returns:
            Message ID if successful, None otherwise
        """
        try:
            # Build recipient list
            if isinstance(to, str):
                to_list = [{"email": to}]
            else:
                to_list = [{"email": email} for email in to]

            if not from_email:
                from_email = "noreply@example.com"

            # Build email payload
            payload: dict[str, Any] = {
                "personalizations": [{"to": to_list}],
                "from": {"email": from_email},
                "subject": subject,
                "content": [{"type": "text/plain", "value": body}],
            }

            if from_name:
                payload["from"]["name"] = from_name

            if html:
                payload["content"].append({"type": "text/html", "value": html})

            if categories:
                payload["categories"] = categories

            if custom_args:
                payload["custom_args"] = custom_args

            # Enable tracking
            payload["tracking_settings"] = {
                "click_tracking": {"enable": True},
                "open_tracking": {"enable": True},
            }

            response = await self._client.post(
                "/mail/send",
                json=payload,
            )

            if response.status_code == 202:
                # SendGrid returns message ID in header
                message_id = response.headers.get("X-Message-Id", "")
                self._logger.info(
                    "sendgrid_email_sent",
                    to=to,
                    message_id=message_id,
                )
                return message_id
            else:
                self._logger.warning(
                    "sendgrid_send_failed",
                    status=response.status_code,
                    response=response.text[:200],
                )
                return None

        except Exception as e:
            self._logger.error("sendgrid_send_error", error=str(e))
            return None

    async def send_template(
        self,
        to: str | list[str],
        template_id: str,
        dynamic_data: dict[str, Any],
        from_email: str | None = None,
        from_name: str | None = None,
        categories: list[str] | None = None,
    ) -> str | None:
        """Send an email using a SendGrid dynamic template.

        Args:
            to: Recipient email(s)
            template_id: SendGrid template ID
            dynamic_data: Template variables
            from_email: Sender email
            from_name: Sender name
            categories: Categories for analytics

        Returns:
            Message ID if successful, None otherwise
        """
        try:
            if isinstance(to, str):
                to_list = [{"email": to}]
            else:
                to_list = [{"email": email} for email in to]

            if not from_email:
                from_email = "noreply@example.com"

            payload: dict[str, Any] = {
                "personalizations": [
                    {
                        "to": to_list,
                        "dynamic_template_data": dynamic_data,
                    }
                ],
                "from": {"email": from_email},
                "template_id": template_id,
            }

            if from_name:
                payload["from"]["name"] = from_name

            if categories:
                payload["categories"] = categories

            response = await self._client.post(
                "/mail/send",
                json=payload,
            )

            if response.status_code == 202:
                message_id = response.headers.get("X-Message-Id", "")
                self._logger.info(
                    "sendgrid_template_sent",
                    template_id=template_id,
                    to=to,
                    message_id=message_id,
                )
                return message_id
            else:
                self._logger.warning("sendgrid_template_send_failed", status=response.status_code)
                return None

        except Exception as e:
            self._logger.error("sendgrid_template_send_error", error=str(e))
            return None

    async def get_stats(
        self,
        start_date: str | None = None,
        end_date: str | None = None,
        aggregated_by: str = "day",
    ) -> MCPQueryResult:
        """Get email statistics.

        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            aggregated_by: "day", "week", or "month"

        Returns:
            Query result with statistics facts
        """
        try:
            if not start_date:
                start_date = (datetime.utcnow() - timedelta(days=7)).strftime("%Y-%m-%d")
            if not end_date:
                end_date = datetime.utcnow().strftime("%Y-%m-%d")

            response = await self._client.get(
                "/stats",
                params={
                    "start_date": start_date,
                    "end_date": end_date,
                    "aggregated_by": aggregated_by,
                },
            )

            if response.status_code != 200:
                raise Exception(f"SendGrid API error {response.status_code}")

            data = response.json()
            facts = []

            # Aggregate totals
            total_requests = 0
            total_delivered = 0
            total_opens = 0
            total_clicks = 0
            total_bounces = 0

            for entry in data:
                stats = entry.get("stats", [{}])[0].get("metrics", {})
                total_requests += stats.get("requests", 0)
                total_delivered += stats.get("delivered", 0)
                total_opens += stats.get("opens", 0)
                total_clicks += stats.get("clicks", 0)
                total_bounces += stats.get("bounces", 0)

            open_rate = (total_opens / total_delivered * 100) if total_delivered > 0 else 0
            click_rate = (total_clicks / total_delivered * 100) if total_delivered > 0 else 0
            delivery_rate = (total_delivered / total_requests * 100) if total_requests > 0 else 0

            facts.append(
                self.create_fact(
                    claim=f"Email stats ({start_date} to {end_date}): {total_requests} sent, {open_rate:.1f}% open rate, {click_rate:.1f}% click rate",
                    fact_type=FactType.CRM_ACTIVITY.value,
                    source_name="SendGrid",
                    source_url="https://app.sendgrid.com/statistics",
                    confidence=0.99,
                    extracted_data={
                        "start_date": start_date,
                        "end_date": end_date,
                        "total_requests": total_requests,
                        "total_delivered": total_delivered,
                        "total_opens": total_opens,
                        "total_clicks": total_clicks,
                        "total_bounces": total_bounces,
                        "open_rate": round(open_rate, 2),
                        "click_rate": round(click_rate, 2),
                        "delivery_rate": round(delivery_rate, 2),
                    },
                )
            )

            return MCPQueryResult(
                facts=facts,
                query=f"stats:{start_date}:{end_date}",
                mcp_server=self.name,
                total_results=1,
            )

        except Exception as e:
            self._logger.error("sendgrid_stats_failed", error=str(e))
            return MCPQueryResult(
                facts=[],
                query="stats",
                mcp_server=self.name,
                errors=[str(e)],
            )

    async def close(self) -> None:
        """Close HTTP client."""
        await self._client.aclose()
