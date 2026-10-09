from __future__ import annotations

import json
from pathlib import Path

from empire_os.architecture_gap_radar import (
    CONTROL,
    architecture_radar,
)


JSON_OUT = (
    CONTROL
    / "architecture_gap_latest.json"
)

FUSION_OUT = (
    CONTROL
    / "detection_fusion_latest.json"
)

MD_OUT = (
    CONTROL
    / "architecture_gap_latest.md"
)


def atomic_json(
    path,
    payload,
):

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    tmp = path.with_suffix(
        ".tmp"
    )

    tmp.write_text(
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
            default=str,
        )
        + "\n",
        encoding="utf-8",
    )

    tmp.replace(
        path
    )


def main():

    result = architecture_radar()

    atomic_json(
        JSON_OUT,
        result,
    )

    atomic_json(
        FUSION_OUT,
        {
            "schema_version":
                "empire-detection-fusion-v1",

            "generated_at":
                result[
                    "generated_at"
                ],

            "lane":
                result[
                    "lane"
                ],

            "authority":
                "OBSERVE",

            "raw_signal_count":
                result[
                    "raw_signal_count"
                ],

            "fused_signal_count":
                result[
                    "fused_signal_count"
                ],

            "signals":
                result[
                    "fused_signals"
                ],

            "entity_risk":
                result[
                    "entity_risk"
                ],
        },
    )

    lines = [
        "# EmpireOS Architecture Gap Radar",
        "",
        (
            "Lane: "
            + result[
                "lane"
            ]
        ),
        (
            "Verdict: "
            + result[
                "lane_verdict"
            ]
        ),
        (
            "Architecture gaps: "
            + str(
                result[
                    "architecture_gap_count"
                ]
            )
        ),
        (
            "Fused detections: "
            + str(
                result[
                    "fused_signal_count"
                ]
            )
        ),
        (
            "Held entities: "
            + str(
                result[
                    "held_entity_count"
                ]
            )
        ),
        "",
    ]

    if result[
        "architecture_gaps"
    ]:

        lines.append(
            "## Architecture gaps"
        )
        lines.append("")

        for gap in result[
            "architecture_gaps"
        ]:

            lines.extend(
                [
                    (
                        "### "
                        + gap[
                            "code"
                        ]
                    ),
                    "",
                    (
                        "- Severity: "
                        + gap[
                            "severity"
                        ]
                    ),
                    (
                        "- Reason: "
                        + gap[
                            "reason"
                        ]
                    ),
                    (
                        "- Recommendation: "
                        + gap[
                            "recommendation"
                        ]
                    ),
                    "",
                ]
            )

    risks = [
        item
        for item
        in result[
            "entity_risk"
        ]
        if item[
            "held"
        ]
    ]

    if risks:

        lines.append(
            "## Highest-risk entities"
        )
        lines.append("")

        for item in risks[:30]:

            lines.extend(
                [
                    (
                        "### "
                        + item[
                            "entity"
                        ]
                    ),
                    "",
                    (
                        "- Severity: "
                        + item[
                            "max_severity"
                        ]
                    ),
                    (
                        "- Signals: "
                        + ", ".join(
                            item[
                                "codes"
                            ]
                        )
                    ),
                    (
                        "- Blocking signals: "
                        + str(
                            item[
                                "blocking_signal_count"
                            ]
                        )
                    ),
                    "",
                ]
            )

    MD_OUT.write_text(
        "\n".join(
            lines
        )
        + "\n",
        encoding="utf-8",
    )

    print(
        json.dumps(
            {
                "status":
                    "PASS",

                "lane_verdict":
                    result[
                        "lane_verdict"
                    ],

                "architecture_gaps":
                    result[
                        "architecture_gap_count"
                    ],

                "active_entities":
                    result.get(
                        "active_entity_count"
                    ),

                "raw_signals":
                    result[
                        "raw_signal_count"
                    ],

                "historical_stale_signals":
                    result.get(
                        "historical_stale_signal_count"
                    ),

                "historical_stale_fused":
                    result.get(
                        "historical_stale_fused_count"
                    ),

                "fused_signals":
                    result[
                        "fused_signal_count"
                    ],

                "critical_entities":
                    result[
                        "critical_entity_count"
                    ],

                "high_entities":
                    result[
                        "high_entity_count"
                    ],

                "held_entities":
                    result[
                        "held_entity_count"
                    ],

                "top_20_risks":
                    result[
                        "entity_risk"
                    ][:20],

                "authority":
                    "OBSERVE",
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
