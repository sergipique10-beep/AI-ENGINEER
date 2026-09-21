"""Generate quality-over-time graphs from eval results."""

from __future__ import annotations

import json
import sys
import io
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

try:
    import matplotlib
    matplotlib.use('Agg')  # Non-interactive backend
    import matplotlib.pyplot as plt
    import matplotlib.ticker as mticker
except ImportError:
    print("matplotlib not installed. Run: pip install matplotlib")
    sys.exit(1)


def generate_radar_chart(results_path: str, output_path: str) -> None:
    """Generate a radar chart of metric scores."""
    with open(results_path, encoding='utf-8') as f:
        data = json.load(f)

    categories = ['Tool Selection', 'Task Completion', 'Tool Validity',
                   'No Hallucination', 'Error Handling', 'Trajectory Quality']
    values = [
        data.get('tool_selection_accuracy', 0),
        data.get('task_completion_rate', 0),
        data.get('tool_validity_rate', 0),
        data.get('no_hallucination_rate', 0),
        data.get('error_handling_rate', 0),
        data.get('trajectory_quality_avg', 0),
    ]

    # Close the radar
    values += values[:1]
    angles = [n / float(len(categories)) * 2 * 3.14159 for n in range(len(categories))]
    angles += angles[:1]

    fig, ax = plt.subplots(figsize=(8, 8), subplot_kw=dict(polar=True))
    ax.plot(angles, values, 'o-', linewidth=2, color='#2196F3', label='Agent')
    ax.fill(angles, values, alpha=0.25, color='#2196F3')

    # Add threshold circle
    threshold_values = [0.85, 0.80, 0.95, 0.90, 0.85, 0.60]
    threshold_values += threshold_values[:1]
    ax.plot(angles, threshold_values, '--', linewidth=1, color='#FF5722', label='Gate Threshold', alpha=0.7)

    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(categories, fontsize=11)
    ax.set_ylim(0, 1.05)
    ax.set_title('Agent Quality Metrics', fontsize=14, fontweight='bold', pad=20)
    ax.legend(loc='upper right', bbox_to_anchor=(1.3, 1.0))
    ax.yaxis.set_major_formatter(mticker.PercentFormatter(xmax=1.0, decimals=0))

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"Radar chart saved to {output_path}")


def generate_comparison_chart(ab_results_path: str, output_path: str) -> None:
    """Generate a grouped bar chart comparing two models."""
    with open(ab_results_path, encoding='utf-8') as f:
        data = json.load(f)

    model_a = data['model_a'].split('/')[-1]
    model_b = data['model_b'].split('/')[-1]

    metrics = ['Tool\nSelection', 'Task\nCompletion', 'Tool\nValidity',
               'No\nHallucination', 'Error\nHandling', 'Trajectory\nQuality']
    values_a = [
        data['results_a']['tool_selection_accuracy'],
        data['results_a']['task_completion_rate'],
        data['results_a'].get('tool_validity_rate', 0),
        data['results_a']['no_hallucination_rate'],
        data['results_a']['error_handling_rate'],
        data['results_a'].get('trajectory_quality_avg', 0),
    ]
    values_b = [
        data['results_b']['tool_selection_accuracy'],
        data['results_b']['task_completion_rate'],
        data['results_b'].get('tool_validity_rate', 0),
        data['results_b']['no_hallucination_rate'],
        data['results_b']['error_handling_rate'],
        data['results_b'].get('trajectory_quality_avg', 0),
    ]

    x = range(len(metrics))
    width = 0.35

    fig, ax = plt.subplots(figsize=(12, 6))
    bars1 = ax.bar([i - width/2 for i in x], values_a, width, label=model_a, color='#2196F3')
    bars2 = ax.bar([i + width/2 for i in x], values_b, width, label=model_b, color='#4CAF50')

    ax.set_ylabel('Score (0-1)')
    ax.set_title('A/B Model Comparison', fontsize=14, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(metrics, fontsize=10)
    ax.set_ylim(0, 1.15)
    ax.legend()
    ax.yaxis.set_major_formatter(mticker.PercentFormatter(xmax=1.0, decimals=0))

    # Add value labels
    for bar in bars1:
        height = bar.get_height()
        ax.annotate(f'{height:.2f}', xy=(bar.get_x() + bar.get_width() / 2, height),
                    xytext=(0, 3), textcoords="offset points", ha='center', fontsize=9)
    for bar in bars2:
        height = bar.get_height()
        ax.annotate(f'{height:.2f}', xy=(bar.get_x() + bar.get_width() / 2, height),
                    xytext=(0, 3), textcoords="offset points", ha='center', fontsize=9)

    # Add threshold lines
    thresholds = [0.85, 0.80, 0.95, 0.90, 0.85, 0.60]
    for i, t in enumerate(thresholds):
        ax.plot([i - 0.5, i + 0.5], [t, t], '--', color='#FF5722', alpha=0.4, linewidth=1)

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"Comparison chart saved to {output_path}")


def generate_category_breakdown(results_path: str, output_path: str) -> None:
    """Generate a bar chart showing performance by category."""
    with open(results_path, encoding='utf-8') as f:
        data = json.load(f)

    cats = data.get('by_category', {})
    if not cats:
        print("No category data found")
        return

    categories = sorted(cats.keys())
    tool_sels = [cats[c]['tool_selection'] / cats[c]['count'] for c in categories]
    task_comps = [cats[c]['task_completion'] / cats[c]['count'] for c in categories]
    counts = [cats[c]['count'] for c in categories]

    fig, ax1 = plt.subplots(figsize=(10, 6))

    x = range(len(categories))
    width = 0.35

    bars1 = ax1.bar([i - width/2 for i in x], tool_sels, width, label='Tool Selection', color='#2196F3')
    bars2 = ax1.bar([i + width/2 for i in x], task_comps, width, label='Task Completion', color='#4CAF50')

    ax1.set_ylabel('Score')
    ax1.set_title('Performance by Category', fontsize=14, fontweight='bold')
    ax1.set_xticks(x)
    ax1.set_xticklabels(categories, rotation=15, ha='right', fontsize=10)
    ax1.set_ylim(0, 1.15)
    ax1.legend()

    # Add case count annotations
    for i, count in enumerate(counts):
        ax1.annotate(f'n={count}', xy=(i, 1.05), ha='center', fontsize=9, color='gray')

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"Category breakdown saved to {output_path}")


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Generate eval visualization charts")
    parser.add_argument("--results", default="data/eval_results.json")
    parser.add_argument("--ab-results", default="data/ab_results.json")
    parser.add_argument("--output-dir", default="data/charts")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if Path(args.results).exists():
        generate_radar_chart(args.results, str(output_dir / "radar.png"))
        generate_category_breakdown(args.results, str(output_dir / "categories.png"))
    else:
        print(f"Results file not found: {args.results}")

    if Path(args.ab_results).exists():
        generate_comparison_chart(args.ab_results, str(output_dir / "ab_comparison.png"))
    else:
        print(f"A/B results file not found: {args.ab_results}")


if __name__ == "__main__":
    main()
