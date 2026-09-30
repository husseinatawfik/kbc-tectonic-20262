// Renders the simulation response. Projections are calculated on the server.

const priceInput = document.querySelector("#car-price");
const downInput = document.querySelector("#down-payment");
const yearsInput = document.querySelector("#loan-years");
const tooltip = document.querySelector("#tooltip");
const chart = document.querySelector("#chart");

const euroWhole = new Intl.NumberFormat("en-GB", {
  style: "currency",
  currency: "EUR",
  maximumFractionDigits: 0,
});

let latest = null;
let requestId = 0;
let pinnedMonth = 36;

function formatEuro(value) {
  const whole = Math.abs(value - Math.round(value)) < 0.001;
  return new Intl.NumberFormat("en-GB", {
    style: "currency",
    currency: "EUR",
    minimumFractionDigits: whole ? 0 : 2,
    maximumFractionDigits: whole ? 0 : 2,
  }).format(value);
}

function months(value) {
  return `${Number(value).toFixed(1)} months`;
}

function syncDownPaymentLimit() {
  const price = Number(priceInput.value);
  downInput.max = String(price);
  if (Number(downInput.value) > price) downInput.value = String(price);
}

function readInputs() {
  syncDownPaymentLimit();
  document.querySelector("#price-out").textContent = euroWhole.format(Number(priceInput.value));
  document.querySelector("#down-out").textContent = euroWhole.format(Number(downInput.value));
  const years = Number(yearsInput.value);
  document.querySelector("#years-out").textContent = `${years} ${years === 1 ? "year" : "years"}`;
  return {
    car_price: Number(priceInput.value),
    down_payment: Number(downInput.value),
    loan_years: years,
  };
}

async function refresh() {
  const inputs = readInputs();
  const id = ++requestId;
  try {
    const response = await fetch("/api/simulate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(inputs),
    });
    const payload = await response.json();
    if (id !== requestId) return;
    if (!response.ok) {
      showError(payload.error || "The simulation could not be updated.");
      return;
    }
    showError("");
    latest = payload;
    render(payload);
  } catch (error) {
    if (id !== requestId) return;
    showError("The simulation could not be reached.");
  }
}

function showError(message) {
  const node = document.querySelector("#error");
  node.hidden = !message;
  node.textContent = message;
}

function render(data) {
  const customer = data.customer;
  const current = data.scenarios.find((scenario) => scenario.id === "current");
  const car = data.scenarios.find((scenario) => scenario.id === "buy_car");

  document.querySelector("#customer-line").textContent = `${customer.name} · fictional customer · synthetic banking data`;
  text("#metric-savings", formatEuro(customer.savings));
  text("#metric-income", formatEuro(customer.monthly_net_income));
  text("#metric-expenses", formatEuro(customer.monthly_expenses));
  text("#expense-breakdown", `${formatEuro(customer.monthly_housing)} housing · ${formatEuro(customer.monthly_fixed_other)} other fixed · ${formatEuro(customer.monthly_variable)} variable`);
  text("#metric-disposable", formatEuro(customer.monthly_disposable_income));
  text("#metric-runway", months(customer.emergency_runway_months));
  text("#runway-goal", `Goal: ${customer.emergency_months_goal} months of expenses`);
  text("#metric-deposit", formatEuro(customer.savings));
  text("#deposit-caption", `${formatEuro(customer.savings)} of ${formatEuro(customer.apartment_goal)}`);
  const meter = document.querySelector("#deposit-meter");
  meter.setAttribute("aria-valuemax", String(customer.apartment_goal));
  meter.setAttribute("aria-valuenow", String(customer.savings));
  document.querySelector("#deposit-bar").style.width = `${Math.min(customer.apartment_progress, 1) * 100}%`;
  text("#today-savings", formatEuro(customer.savings));
  text("#rate-note", `Mock rate ${data.assumptions.annual_interest_rate_label}. Change the price, the down payment, or the term.`);
  text("#assumption-note", data.assumptions.note);
  text("#financed-line", `${formatEuro(car.amount_financed)} financed · ${formatEuro(car.monthly_loan_payment)} each month · down payment leaves ${formatEuro(car.savings_after_down_payment)} before that month's saving.`);

  fillFacts("#current-facts", current);
  fillFacts("#car-facts", car);
  renderStatements("#statements", data.comparison.statements, true);
  renderStatements("#peer-statements", data.peers.statements, false);
  text("#peer-disclaimer", data.peers.disclaimer);
  const traits = document.querySelector("#traits");
  traits.replaceChildren();
  data.peers.traits.forEach((trait) => {
    const item = document.createElement("li");
    item.textContent = trait;
    traits.append(item);
  });
  drawChart(current.series, car.series, customer.apartment_goal);
  showMonth(pinnedMonth);
}

function fillFacts(selector, scenario) {
  const rows = [
    ["Savings after 1 year", formatEuro(scenario.savings_after_1_year)],
    ["Savings after 3 years", formatEuro(scenario.savings_after_3_years)],
    ["Monthly disposable income", formatEuro(scenario.monthly_disposable_income)],
    ["Emergency runway in 3 years", months(scenario.emergency_runway_after_3_years)],
    ["Apartment deposit", scenario.apartment_goal_label],
  ];
  const list = document.querySelector(selector);
  list.replaceChildren();
  rows.forEach(([label, value]) => {
    const row = document.createElement("div");
    row.className = "fact";
    const term = document.createElement("dt");
    term.textContent = label;
    const detail = document.createElement("dd");
    const strong = document.createElement("strong");
    strong.textContent = value;
    detail.append(strong);
    row.append(term, detail);
    list.append(row);
  });
}

function renderStatements(selector, statements, asList) {
  const host = document.querySelector(selector);
  host.replaceChildren();
  statements.forEach((statement) => {
    const node = document.createElement(asList ? "li" : "p");
    if (!asList) node.className = "peer-line";
    node.textContent = statement;
    host.append(node);
  });
}

function text(selector, value) {
  document.querySelector(selector).textContent = value;
}

function drawChart(currentSeries, carSeries, goal) {
  const width = 860;
  const height = 390;
  const pad = { left: 72, right: 18, top: 26, bottom: 36 };
  const savings = currentSeries.concat(carSeries).map((point) => point.savings);
  let min = Math.min(0, ...savings);
  let max = Math.max(goal, ...savings);
  const span = max - min || 1;
  min -= span * 0.06;
  max += span * 0.1;
  const lastMonth = currentSeries[currentSeries.length - 1].month;
  const x = (month) => pad.left + (month / lastMonth) * (width - pad.left - pad.right);
  const y = (value) => pad.top + ((max - value) / (max - min)) * (height - pad.top - pad.bottom);
  const step = span > 50000 ? 10000 : 5000;
  const ticks = [];
  for (let value = Math.ceil(min / step) * step; value <= max; value += step) ticks.push(value);

  const parts = [];
  ticks.forEach((value) => {
    parts.push(`<line class="chart-grid" x1="${pad.left}" x2="${width - pad.right}" y1="${y(value)}" y2="${y(value)}"></line>`);
    parts.push(`<text class="axis-label" x="${pad.left - 8}" y="${y(value) + 4}" text-anchor="end">${euroWhole.format(value)}</text>`);
  });
  [0, 12, 24, 36].forEach((month) => {
    if (month > lastMonth) return;
    parts.push(`<text class="axis-label" x="${x(month)}" y="${height - 12}" text-anchor="middle">${month === 0 ? "Today" : `${month}m`}</text>`);
  });
  parts.push(`<line class="chart-goal" x1="${pad.left}" x2="${width - pad.right}" y1="${y(goal)}" y2="${y(goal)}"></line>`);
  parts.push(`<text class="goal-label" x="${pad.left + 8}" y="${Math.max(16, y(goal) - 8)}">Apartment ${euroWhole.format(goal)}</text>`);
  parts.push(`<path class="series-current" d="${linePath(currentSeries, x, y)}"></path>`);
  parts.push(`<path class="series-car" d="${linePath(carSeries, x, y)}"></path>`);
  parts.push(`<circle cx="${x(0)}" cy="${y(currentSeries[0].savings)}" r="4" fill="#14283f"></circle>`);
  chart.innerHTML = parts.join("");
  chart.dataset.min = String(min);
  chart.dataset.max = String(max);
  chart.dataset.last = String(lastMonth);
}

function linePath(series, x, y) {
  return series.map((point, index) => `${index === 0 ? "M" : "L"} ${x(point.month).toFixed(1)} ${y(point.savings).toFixed(1)}`).join(" ");
}

function monthFromEvent(event) {
  if (!latest) return 0;
  const bounds = chart.getBoundingClientRect();
  const last = Number(chart.dataset.last || 36);
  const ratio = Math.min(1, Math.max(0, (event.clientX - bounds.left) / bounds.width));
  const viewX = ratio * 860;
  const padLeft = 72;
  const padRight = 18;
  const monthRatio = (viewX - padLeft) / (860 - padLeft - padRight);
  return Math.min(last, Math.max(0, Math.round(monthRatio * last)));
}

function showMonth(month) {
  if (!latest) return;
  const current = latest.scenarios[0].series[month];
  const car = latest.scenarios[1].series[month];
  if (!current || !car) return;
  const when = month === 0 ? "Today" : `Month ${month}`;
  document.querySelector("#chart-readout").textContent =
    `${when}: Current Path ${formatEuro(current.savings)} · Buy the car ${formatEuro(car.savings)} · disposable ${formatEuro(current.monthly_disposable_income)} vs ${formatEuro(car.monthly_disposable_income)}`;
}

chart.addEventListener("pointermove", (event) => {
  if (!latest) return;
  const month = monthFromEvent(event);
  const current = latest.scenarios[0].series[month];
  const car = latest.scenarios[1].series[month];
  const frame = chart.getBoundingClientRect();
  tooltip.hidden = false;
  tooltip.style.left = `${event.clientX - frame.left}px`;
  tooltip.style.top = `${event.clientY - frame.top}px`;
  tooltip.innerHTML = `Month ${month}<br>Current Path ${formatEuro(current.savings)}<br>Buy the car ${formatEuro(car.savings)}`;
  showMonth(month);
});

chart.addEventListener("pointerleave", () => {
  tooltip.hidden = true;
  showMonth(pinnedMonth);
});

chart.addEventListener("click", (event) => {
  pinnedMonth = monthFromEvent(event);
  showMonth(pinnedMonth);
});

[priceInput, downInput, yearsInput].forEach((input) => {
  input.addEventListener("input", refresh);
});

refresh();
