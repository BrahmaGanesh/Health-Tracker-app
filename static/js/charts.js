/* ============================================================
   ADAPTIVE HEALTH MANAGEMENT PLATFORM
   charts.js — Reusable Chart.js Helpers
   ============================================================ */

'use strict';

// ════════════════════════════════════════════════════════════
// THEME — reads CSS variables for consistent colors
// ════════════════════════════════════════════════════════════

const ChartTheme = {
  get(prop) {
    return getComputedStyle(document.documentElement)
      .getPropertyValue(prop).trim();
  },

  colors: {
    navy:    '#142d4c',
    mint:    '#9fd3c7',
    gold:    '#f8da5b',
    sage:    '#61b390',
    violet:  '#4f3b78',
    peach:   '#ebcbae',
    red:     '#ef4444',
    blue:    '#3b82f6',
    green:   '#22c55e',
    yellow:  '#f59e0b',
    purple:  '#8b5cf6',
    teal:    '#14b8a6',
  },

  get textMuted() {
    return this.get('--text-muted') || '#6b7280';
  },
  get border() {
    return this.get('--border') || '#e5e7eb';
  },
  get cardBg() {
    return this.get('--card-bg') || '#ffffff';
  },
};


// ════════════════════════════════════════════════════════════
// DEFAULT CHART OPTIONS
// ════════════════════════════════════════════════════════════

const defaultOptions = {
  responsive: true,
  maintainAspectRatio: true,
  interaction: { mode: 'index', intersect: false },

  plugins: {
    legend: { display: false },
    tooltip: {
      backgroundColor: '#142d4c',
      titleColor:      '#e8edf5',
      bodyColor:       '#adc4e0',
      borderColor:     'rgba(159,211,199,0.2)',
      borderWidth:     1,
      padding:         12,
      cornerRadius:    10,
      usePointStyle:   true,
    }
  },

  scales: {
    x: {
      grid:  { color: 'rgba(0,0,0,0.04)', drawBorder: false },
      ticks: { color: ChartTheme.textMuted, font: { size: 11, family: "'DM Sans'" } },
      border: { display: false },
    },
    y: {
      grid:  { color: 'rgba(0,0,0,0.04)', drawBorder: false },
      ticks: { color: ChartTheme.textMuted, font: { size: 11, family: "'DM Sans'" } },
      border: { display: false },
      beginAtZero: false,
    }
  },

  elements: {
    line:  { tension: 0.4, borderWidth: 2.5 },
    point: { radius: 3, hoverRadius: 6, borderWidth: 2 }
  },

  animation: {
    duration: 800,
    easing:   'easeOutQuart',
  }
};


// ════════════════════════════════════════════════════════════
// CHART FACTORY — Creates & returns chart instances
// ════════════════════════════════════════════════════════════

const ChartFactory = {
  instances: {},

  create(canvasId, config) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) return null;

    // Destroy previous if exists
    if (this.instances[canvasId]) {
      this.instances[canvasId].destroy();
    }

    const chart = new Chart(ctx, config);
    this.instances[canvasId] = chart;
    return chart;
  },

  destroy(canvasId) {
    if (this.instances[canvasId]) {
      this.instances[canvasId].destroy();
      delete this.instances[canvasId];
    }
  },

  update(canvasId, labels, datasets) {
    const chart = this.instances[canvasId];
    if (!chart) return;
    chart.data.labels   = labels;
    chart.data.datasets = datasets;
    chart.update();
  }
};


// ════════════════════════════════════════════════════════════
// BP TREND CHART
// ════════════════════════════════════════════════════════════

function createBpChart(canvasId, data, options = {}) {
  const labels = data.map(d => d.day);
  const sys    = data.map(d => d.sys);
  const dia    = data.map(d => d.dia);
  const pulse  = data.map(d => d.pulse || null);

  const sysTgt  = options.targetSys  || 130;
  const diaTgt  = options.targetDia  || 80;

  return ChartFactory.create(canvasId, {
    type: 'line',
    data: {
      labels,
      datasets: [
        {
          label:           'Systolic',
          data:            sys,
          borderColor:     ChartTheme.colors.red,
          backgroundColor: 'rgba(239,68,68,0.07)',
          pointBackgroundColor: ChartTheme.colors.red,
          fill:            true,
          spanGaps:        true,
        },
        {
          label:           'Diastolic',
          data:            dia,
          borderColor:     ChartTheme.colors.blue,
          backgroundColor: 'rgba(59,130,246,0.05)',
          pointBackgroundColor: ChartTheme.colors.blue,
          fill:            true,
          spanGaps:        true,
        },
        {
          label:           'Pulse',
          data:            pulse,
          borderColor:     ChartTheme.colors.sage,
          backgroundColor: 'transparent',
          borderDash:      [5, 4],
          borderWidth:     2,
          pointBackgroundColor: ChartTheme.colors.sage,
          pointRadius:     3,
          fill:            false,
          spanGaps:        true,
        }
      ]
    },
    options: {
      ...defaultOptions,
      plugins: {
        ...defaultOptions.plugins,
        tooltip: {
          ...defaultOptions.plugins.tooltip,
          callbacks: {
            label: ctx => {
              const u = ctx.dataset.label === 'Pulse' ? ' bpm' : ' mmHg';
              return ` ${ctx.dataset.label}: ${ctx.parsed.y}${u}`;
            }
          }
        }
      },
      scales: {
        ...defaultOptions.scales,
        y: { ...defaultOptions.scales.y, min: 50, suggestedMax: 200 }
      }
    }
  });
}


// ════════════════════════════════════════════════════════════
// WEIGHT TREND CHART
// ════════════════════════════════════════════════════════════

function createWeightChart(canvasId, data, targetWeight = null) {
  const labels  = data.map(d => d.day);
  const weights = data.map(d => d.weight);

  const datasets = [
    {
      label:           'Weight (kg)',
      data:            weights,
      borderColor:     ChartTheme.colors.violet,
      backgroundColor: 'rgba(79,59,120,0.08)',
      pointBackgroundColor: ChartTheme.colors.violet,
      fill:            true,
      spanGaps:        true,
    }
  ];

  if (targetWeight) {
    datasets.push({
      label:       'Target',
      data:        labels.map(() => targetWeight),
      borderColor: ChartTheme.colors.sage,
      borderDash:  [6, 4],
      borderWidth: 1.5,
      pointRadius: 0,
      fill:        false,
    });
  }

  return ChartFactory.create(canvasId, {
    type: 'line',
    data: { labels, datasets },
    options: {
      ...defaultOptions,
      plugins: {
        ...defaultOptions.plugins,
        tooltip: {
          ...defaultOptions.plugins.tooltip,
          callbacks: {
            label: ctx => ` ${ctx.dataset.label}: ${ctx.parsed.y} kg`
          }
        }
      },
      scales: {
        ...defaultOptions.scales,
        y: { ...defaultOptions.scales.y, beginAtZero: false }
      }
    }
  });
}


// ════════════════════════════════════════════════════════════
// WATER / BAR CHART
// ════════════════════════════════════════════════════════════

function createWaterChart(canvasId, data, target = 2.5) {
  const labels = data.map(d => d.day);
  const values = data.map(d => d.litres);

  const barColors = values.map(v =>
    v >= target    ? 'rgba(97,179,144,0.85)'  :
    v >= target * 0.6 ? 'rgba(248,218,91,0.85)' :
    'rgba(235,203,174,0.85)'
  );

  return ChartFactory.create(canvasId, {
    type: 'bar',
    data: {
      labels,
      datasets: [
        {
          label:           'Water (L)',
          data:            values,
          backgroundColor: barColors,
          borderColor:     barColors.map(c => c.replace('0.85', '1')),
          borderWidth:     1,
          borderRadius:    8,
        },
        {
          label:       'Target',
          data:        labels.map(() => target),
          type:        'line',
          borderColor: ChartTheme.colors.sage,
          borderDash:  [6, 4],
          borderWidth: 1.5,
          pointRadius: 0,
          fill:        false,
        }
      ]
    },
    options: {
      ...defaultOptions,
      plugins: {
        ...defaultOptions.plugins,
        tooltip: {
          ...defaultOptions.plugins.tooltip,
          callbacks: {
            label: ctx => ` ${ctx.dataset.label}: ${ctx.parsed.y}L`
          }
        }
      },
      scales: {
        ...defaultOptions.scales,
        y: { ...defaultOptions.scales.y, beginAtZero: true, suggestedMax: target * 1.5 }
      }
    }
  });
}


// ════════════════════════════════════════════════════════════
// NUTRITION CHART (multi-line)
// ════════════════════════════════════════════════════════════

function createNutritionChart(canvasId, data) {
  const labels   = data.map(d => d.day);
  const calories = data.map(d => d.calories);
  const protein  = data.map(d => d.protein);
  const fiber    = data.map(d => d.fiber);

  return ChartFactory.create(canvasId, {
    type: 'line',
    data: {
      labels,
      datasets: [
        {
          label:           'Calories',
          data:            calories,
          borderColor:     ChartTheme.colors.red,
          backgroundColor: 'rgba(239,68,68,0.06)',
          fill:            true,
          yAxisID:         'y',
          spanGaps:        true,
        },
        {
          label:           'Protein (g)',
          data:            protein,
          borderColor:     ChartTheme.colors.sage,
          backgroundColor: 'transparent',
          yAxisID:         'y1',
          borderDash:      [4, 3],
          spanGaps:        true,
        },
        {
          label:           'Fiber (g)',
          data:            fiber,
          borderColor:     ChartTheme.colors.violet,
          backgroundColor: 'transparent',
          yAxisID:         'y1',
          borderDash:      [2, 3],
          borderWidth:     2,
          pointRadius:     2,
          spanGaps:        true,
        }
      ]
    },
    options: {
      ...defaultOptions,
      scales: {
        x: defaultOptions.scales.x,
        y: {
          ...defaultOptions.scales.y,
          position: 'left',
          title:    { display: true, text: 'Calories', color: ChartTheme.textMuted, font: { size: 11 } }
        },
        y1: {
          ...defaultOptions.scales.y,
          position: 'right',
          grid:     { drawOnChartArea: false },
          title:    { display: true, text: 'Grams', color: ChartTheme.textMuted, font: { size: 11 } }
        }
      }
    }
  });
}


// ════════════════════════════════════════════════════════════
// SUGAR CHART
// ════════════════════════════════════════════════════════════

function createSugarChart(canvasId, data) {
  const labels   = data.map(d => d.day);
  const fasting  = data.map(d => d.fasting);
  const postmeal = data.map(d => d.postmeal);

  return ChartFactory.create(canvasId, {
    type: 'line',
    data: {
      labels,
      datasets: [
        {
          label:           'Fasting (mg/dL)',
          data:            fasting,
          borderColor:     ChartTheme.colors.orange || '#f97316',
          backgroundColor: 'rgba(249,115,22,0.07)',
          pointBackgroundColor: ChartTheme.colors.orange || '#f97316',
          fill:            true,
          spanGaps:        true,
        },
        {
          label:           'Post-Meal (mg/dL)',
          data:            postmeal,
          borderColor:     ChartTheme.colors.yellow,
          backgroundColor: 'transparent',
          borderDash:      [5, 4],
          pointBackgroundColor: ChartTheme.colors.yellow,
          fill:            false,
          spanGaps:        true,
        }
      ]
    },
    options: {
      ...defaultOptions,
      plugins: {
        ...defaultOptions.plugins,
        tooltip: {
          ...defaultOptions.plugins.tooltip,
          callbacks: {
            label: ctx => ` ${ctx.dataset.label}: ${ctx.parsed.y} mg/dL`
          }
        }
      },
      scales: {
        ...defaultOptions.scales,
        y: { ...defaultOptions.scales.y, beginAtZero: false, suggestedMin: 60 }
      }
    }
  });
}


// ════════════════════════════════════════════════════════════
// DONUT / PIE CHART — for macro breakdown
// ════════════════════════════════════════════════════════════

function createMacroDonut(canvasId, protein, carbs, fats) {
  return ChartFactory.create(canvasId, {
    type: 'doughnut',
    data: {
      labels:   ['Protein', 'Carbs', 'Fats'],
      datasets: [{
        data:            [protein, carbs, fats],
        backgroundColor: [
          'rgba(97,179,144,0.85)',
          'rgba(248,218,91,0.85)',
          'rgba(159,211,199,0.85)',
        ],
        borderColor: [
          ChartTheme.colors.sage,
          '#d4a017',
          ChartTheme.colors.mint,
        ],
        borderWidth: 2,
        hoverOffset: 6,
      }]
    },
    options: {
      responsive:  true,
      cutout:      '68%',
      plugins: {
        legend: {
          display:  true,
          position: 'bottom',
          labels: {
            font:        { size: 12, family: "'DM Sans'" },
            color:       ChartTheme.textMuted,
            padding:     16,
            usePointStyle: true,
            pointStyle: 'circle',
          }
        },
        tooltip: {
          ...defaultOptions.plugins.tooltip,
          callbacks: {
            label: ctx => ` ${ctx.label}: ${ctx.parsed}g`
          }
        }
      },
      animation: { animateRotate: true, duration: 900 }
    }
  });
}


// ════════════════════════════════════════════════════════════
// HEALTH SCORE TREND
// ════════════════════════════════════════════════════════════

function createScoreChart(canvasId, data) {
  const labels = data.map(d => d.day);
  const scores = data.map(d => d.score);

  return ChartFactory.create(canvasId, {
    type: 'line',
    data: {
      labels,
      datasets: [{
        label:           'Health Score',
        data:            scores,
        borderColor:     ChartTheme.colors.sage,
        backgroundColor: 'rgba(97,179,144,0.12)',
        pointBackgroundColor: ChartTheme.colors.sage,
        fill:            true,
        spanGaps:        true,
      }]
    },
    options: {
      ...defaultOptions,
      plugins: {
        ...defaultOptions.plugins,
        tooltip: {
          ...defaultOptions.plugins.tooltip,
          callbacks: {
            label: ctx => ` Score: ${ctx.parsed.y}%`
          }
        }
      },
      scales: {
        ...defaultOptions.scales,
        y: { ...defaultOptions.scales.y, min: 0, max: 100, beginAtZero: true }
      }
    }
  });
}


// ════════════════════════════════════════════════════════════
// EXPORT
// ════════════════════════════════════════════════════════════

window.HealthCharts = {
  createBpChart,
  createWeightChart,
  createWaterChart,
  createNutritionChart,
  createSugarChart,
  createMacroDonut,
  createScoreChart,
  ChartFactory,
  ChartTheme,
};