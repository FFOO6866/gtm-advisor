"""Clustering Algorithms for Market Segmentation.

Uses simplified k-means and rule-based clustering for:
- Firmographic clustering (company similarity)
- Persona clustering (buyer similarity)
- Market segmentation (opportunity grouping)

Note: For production, consider scikit-learn or HDBSCAN.
This implementation provides interpretable, dependency-light clustering.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
import math
from collections import defaultdict


@dataclass
class Cluster:
    """A cluster of similar items."""
    id: str
    name: str
    centroid: dict[str, float]
    members: list[dict[str, Any]] = field(default_factory=list)
    characteristics: list[str] = field(default_factory=list)
    size: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "size": self.size,
            "characteristics": self.characteristics,
            "centroid": self.centroid,
        }


@dataclass
class ClusteringResult:
    """Result of clustering operation."""
    clusters: list[Cluster]
    unclustered: list[dict[str, Any]]
    quality_score: float  # 0-1, based on cluster cohesion
    method: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "clusters": [c.to_dict() for c in self.clusters],
            "unclustered_count": len(self.unclustered),
            "quality_score": round(self.quality_score, 3),
            "method": self.method,
        }


class FirmographicClusterer:
    """Cluster companies by firmographic similarity.

    Uses rule-based clustering with optional k-means refinement.
    """

    # Standard firmographic buckets
    SIZE_BUCKETS = ["micro", "small", "medium", "large", "enterprise"]
    STAGE_BUCKETS = ["early", "growth", "scale", "mature"]

    def __init__(
        self,
        n_clusters: int = 5,
        min_cluster_size: int = 3,
    ):
        self.n_clusters = n_clusters
        self.min_cluster_size = min_cluster_size

    def cluster(self, companies: list[dict[str, Any]]) -> ClusteringResult:
        """Cluster companies by firmographic features.

        Args:
            companies: List of company dicts with:
                - employee_count: int
                - industry: str
                - stage: str
                - location: str
                - revenue: float (optional)

        Returns:
            Clustering result
        """
        if len(companies) < self.min_cluster_size:
            return ClusteringResult(
                clusters=[],
                unclustered=companies,
                quality_score=0.0,
                method="rule_based",
            )

        # Step 1: Normalize features
        normalized = [self._normalize_company(c) for c in companies]

        # Step 2: Rule-based initial clustering (industry x size)
        initial_clusters = self._rule_based_cluster(companies, normalized)

        # Step 3: Merge small clusters
        merged = self._merge_small_clusters(initial_clusters)

        # Step 4: Calculate quality
        quality = self._calculate_quality(merged)

        return ClusteringResult(
            clusters=merged,
            unclustered=[],
            quality_score=quality,
            method="rule_based_firmographic",
        )

    def _normalize_company(self, company: dict[str, Any]) -> dict[str, float]:
        """Normalize company to feature vector."""
        features = {}

        # Size (normalized 0-1)
        emp = company.get("employee_count", 0)
        if isinstance(emp, str):
            # Parse range like "11-50"
            try:
                emp = int(emp.split("-")[0])
            except (ValueError, IndexError):
                emp = 50
        features["size"] = min(emp / 1000, 1.0)

        # Stage (ordinal encoding)
        stage = company.get("stage", "").lower()
        stage_map = {"seed": 0.2, "series_a": 0.4, "series_b": 0.6, "series_c": 0.8, "public": 1.0}
        features["stage"] = stage_map.get(stage, 0.5)

        # Revenue (log-normalized)
        revenue = company.get("revenue", 0)
        if revenue > 0:
            features["revenue"] = min(math.log10(revenue + 1) / 9, 1.0)  # Normalize to ~$1B max
        else:
            features["revenue"] = 0.3  # Default for unknown

        return features

    def _rule_based_cluster(
        self,
        companies: list[dict[str, Any]],
        normalized: list[dict[str, float]],
    ) -> list[Cluster]:
        """Create clusters based on industry and size rules."""
        # Group by industry + size bucket
        groups: dict[str, list[tuple[dict, dict]]] = defaultdict(list)

        for company, norm in zip(companies, normalized):
            industry = company.get("industry", "other").lower()
            size_bucket = self._get_size_bucket(company.get("employee_count", 0))
            key = f"{industry}_{size_bucket}"
            groups[key].append((company, norm))

        # Convert to clusters
        clusters = []
        for i, (key, members) in enumerate(groups.items()):
            if len(members) >= self.min_cluster_size:
                industry, size = key.rsplit("_", 1)

                # Calculate centroid
                centroid = {}
                for feature in ["size", "stage", "revenue"]:
                    values = [m[1].get(feature, 0) for m in members]
                    centroid[feature] = sum(values) / len(values) if values else 0

                cluster = Cluster(
                    id=f"cluster_{i}",
                    name=f"{industry.title()} - {size.title()}",
                    centroid=centroid,
                    members=[m[0] for m in members],
                    characteristics=[
                        f"Industry: {industry}",
                        f"Size: {size}",
                        f"Avg stage: {centroid.get('stage', 0):.2f}",
                    ],
                    size=len(members),
                )
                clusters.append(cluster)

        return clusters

    def _get_size_bucket(self, employee_count: Any) -> str:
        """Get size bucket from employee count."""
        if isinstance(employee_count, str):
            try:
                employee_count = int(employee_count.split("-")[0])
            except (ValueError, IndexError):
                return "small"

        if employee_count <= 10:
            return "micro"
        elif employee_count <= 50:
            return "small"
        elif employee_count <= 200:
            return "medium"
        elif employee_count <= 1000:
            return "large"
        else:
            return "enterprise"

    def _merge_small_clusters(self, clusters: list[Cluster]) -> list[Cluster]:
        """Merge clusters below minimum size."""
        large_enough = [c for c in clusters if c.size >= self.min_cluster_size]
        too_small = [c for c in clusters if c.size < self.min_cluster_size]

        # Try to merge small clusters into nearest large cluster
        for small in too_small:
            if not large_enough:
                large_enough.append(small)
                continue

            # Find nearest cluster by centroid distance
            min_dist = float('inf')
            nearest = large_enough[0]
            for large in large_enough:
                dist = self._centroid_distance(small.centroid, large.centroid)
                if dist < min_dist:
                    min_dist = dist
                    nearest = large

            # Merge
            nearest.members.extend(small.members)
            nearest.size = len(nearest.members)

        return large_enough

    def _centroid_distance(self, c1: dict[str, float], c2: dict[str, float]) -> float:
        """Calculate distance between centroids."""
        dist = 0.0
        for key in c1:
            if key in c2:
                dist += (c1[key] - c2[key]) ** 2
        return math.sqrt(dist)

    def _calculate_quality(self, clusters: list[Cluster]) -> float:
        """Calculate clustering quality (cohesion)."""
        if not clusters:
            return 0.0

        # Average within-cluster variance
        total_variance = 0.0
        total_members = 0

        for cluster in clusters:
            if cluster.size < 2:
                continue

            # Calculate variance from centroid
            for member in cluster.members:
                norm = self._normalize_company(member)
                dist = self._centroid_distance(norm, cluster.centroid)
                total_variance += dist
                total_members += 1

        if total_members == 0:
            return 0.5

        avg_variance = total_variance / total_members
        # Convert to quality score (lower variance = higher quality)
        quality = max(0, 1 - avg_variance)
        return quality


class PersonaClusterer:
    """Cluster buyers into personas based on behavior and preferences."""

    def __init__(
        self,
        n_personas: int = 4,
        min_persona_size: int = 5,
    ):
        self.n_personas = n_personas
        self.min_persona_size = min_persona_size

    def cluster(self, buyers: list[dict[str, Any]]) -> ClusteringResult:
        """Cluster buyers into personas.

        Args:
            buyers: List of buyer dicts with:
                - title: str
                - seniority: str
                - priorities: list[str]
                - pain_points: list[str]
                - content_preferences: list[str]

        Returns:
            Persona clusters
        """
        if len(buyers) < self.min_persona_size:
            return ClusteringResult(
                clusters=[],
                unclustered=buyers,
                quality_score=0.0,
                method="rule_based_persona",
            )

        # Cluster by seniority and role
        groups: dict[str, list[dict]] = defaultdict(list)

        for buyer in buyers:
            seniority = buyer.get("seniority", "mid").lower()
            role_type = self._classify_role(buyer.get("title", ""))
            key = f"{seniority}_{role_type}"
            groups[key].append(buyer)

        # Convert to persona clusters
        clusters = []
        persona_names = {
            "executive_business": "Strategic Decision Maker",
            "executive_technical": "Technical Executive",
            "senior_business": "Business Leader",
            "senior_technical": "Technical Lead",
            "mid_business": "Business Practitioner",
            "mid_technical": "Technical Practitioner",
        }

        for i, (key, members) in enumerate(groups.items()):
            if len(members) >= self.min_persona_size:
                # Aggregate characteristics
                all_priorities = []
                all_pain_points = []
                for m in members:
                    all_priorities.extend(m.get("priorities", []))
                    all_pain_points.extend(m.get("pain_points", []))

                # Top characteristics
                top_priorities = self._top_items(all_priorities, 3)
                top_pain_points = self._top_items(all_pain_points, 3)

                cluster = Cluster(
                    id=f"persona_{i}",
                    name=persona_names.get(key, f"Persona {i+1}"),
                    centroid={},  # Not applicable for categorical
                    members=members,
                    characteristics=[
                        f"Top priorities: {', '.join(top_priorities)}",
                        f"Key pain points: {', '.join(top_pain_points)}",
                    ],
                    size=len(members),
                )
                clusters.append(cluster)

        return ClusteringResult(
            clusters=clusters,
            unclustered=[],
            quality_score=0.7 if clusters else 0.0,
            method="rule_based_persona",
        )

    def _classify_role(self, title: str) -> str:
        """Classify role as business or technical."""
        title_lower = title.lower()

        technical_keywords = [
            "engineer", "developer", "architect", "tech", "data",
            "devops", "infrastructure", "security", "product"
        ]
        business_keywords = [
            "sales", "marketing", "finance", "hr", "operations",
            "business", "strategy", "growth", "revenue"
        ]

        if any(k in title_lower for k in technical_keywords):
            return "technical"
        elif any(k in title_lower for k in business_keywords):
            return "business"
        else:
            return "business"  # Default

    def _top_items(self, items: list[str], n: int) -> list[str]:
        """Get top n most common items."""
        counts: dict[str, int] = defaultdict(int)
        for item in items:
            counts[item.lower()] += 1
        sorted_items = sorted(counts.items(), key=lambda x: x[1], reverse=True)
        return [item for item, _ in sorted_items[:n]]


class MarketSegmenter:
    """Segment market into opportunity groups.

    Combines firmographic and behavioral signals.
    """

    def __init__(
        self,
        min_segment_size: int = 10,
        max_segments: int = 6,
    ):
        self.min_segment_size = min_segment_size
        self.max_segments = max_segments

    def segment(
        self,
        companies: list[dict[str, Any]],
        your_value_props: list[str],
    ) -> ClusteringResult:
        """Segment market by opportunity fit.

        Args:
            companies: List of potential market companies
            your_value_props: Your key value propositions

        Returns:
            Market segments ranked by opportunity
        """
        # Score each company's opportunity fit
        scored = []
        for company in companies:
            opp_score = self._opportunity_score(company, your_value_props)
            scored.append((company, opp_score))

        # Sort by score
        scored.sort(key=lambda x: x[1], reverse=True)

        # Create segments by score quartile
        n = len(scored)
        if n < self.min_segment_size:
            return ClusteringResult(
                clusters=[],
                unclustered=companies,
                quality_score=0.0,
                method="opportunity_segmentation",
            )

        segments = []
        quartile_size = n // 4

        segment_defs = [
            ("high_priority", "High Priority Targets", 0, quartile_size),
            ("strong_fit", "Strong Fit", quartile_size, quartile_size * 2),
            ("moderate_fit", "Moderate Fit", quartile_size * 2, quartile_size * 3),
            ("nurture", "Nurture/Long-term", quartile_size * 3, n),
        ]

        for seg_id, name, start, end in segment_defs:
            members = [s[0] for s in scored[start:end]]
            if len(members) >= self.min_segment_size:
                avg_score = sum(s[1] for s in scored[start:end]) / len(members)

                segments.append(Cluster(
                    id=seg_id,
                    name=name,
                    centroid={"opportunity_score": avg_score},
                    members=members,
                    characteristics=[
                        f"Avg opportunity score: {avg_score:.2f}",
                        f"Count: {len(members)}",
                    ],
                    size=len(members),
                ))

        return ClusteringResult(
            clusters=segments[:self.max_segments],
            unclustered=[],
            quality_score=0.75,
            method="opportunity_segmentation",
        )

    def _opportunity_score(
        self,
        company: dict[str, Any],
        value_props: list[str],
    ) -> float:
        """Score opportunity based on fit and timing."""
        score = 0.0

        # Pain point alignment
        company_pains = company.get("pain_points", [])
        pain_match = sum(1 for vp in value_props if any(vp.lower() in p.lower() for p in company_pains))
        score += min(pain_match * 0.15, 0.30)

        # Budget signals
        if company.get("funding_raised") or company.get("revenue"):
            score += 0.20

        # Growth signals
        growth = company.get("growth_signals", [])
        score += min(len(growth) * 0.05, 0.20)

        # Size fit (mid-market is often best)
        emp = company.get("employee_count", 0)
        if isinstance(emp, str):
            try:
                emp = int(emp.split("-")[0])
            except:
                emp = 50
        if 20 <= emp <= 500:
            score += 0.15
        elif emp < 20:
            score += 0.05

        # Timing
        if "hiring" in str(company.get("signals", [])).lower():
            score += 0.10
        if "expansion" in str(company.get("signals", [])).lower():
            score += 0.10

        return min(score, 1.0)
