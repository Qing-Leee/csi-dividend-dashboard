(function() {
  var style = getComputedStyle(document.documentElement);
  var accent = style.getPropertyValue('--accent').trim();
  var accent2 = style.getPropertyValue('--accent2').trim();
  var ink = style.getPropertyValue('--ink').trim();
  var muted = style.getPropertyValue('--muted').trim();
  var rule = style.getPropertyValue('--rule').trim();
  var bg2 = style.getPropertyValue('--bg2').trim();
  var bg3 = style.getPropertyValue('--bg3').trim();
  var green = style.getPropertyValue('--green').trim();
  var red = style.getPropertyValue('--red').trim();
  var yellow = style.getPropertyValue('--yellow').trim();
  var blue = style.getPropertyValue('--blue').trim();
  var purple = style.getPropertyValue('--purple').trim();

  var palette = [accent, accent2, blue, yellow, purple, green, red];

  var commonGrid = {
    left: '8%',
    right: '8%',
    top: '12%',
    bottom: '15%'
  };

  var commonAxisLabel = { color: muted, fontSize: 11 };
  var commonAxisLine = { lineStyle: { color: rule } };
  var commonSplitLine = { lineStyle: { color: rule, type: 'dashed', opacity: 0.3 } };

  // ===== Fallback data (original hardcoded values) =====
  var fallbackDates = ['05-29', '06-10', '06-23', '07-10', '07-12', '07-14', '07-16', '07-17', '07-20'];
  var fallbackInvestments = [1000, 500, 1000, 500, 200, 200, 400, 200, 0];
  var fallbackIndexLevels = [5683.85, 5588.98, 5342.69, 5184.10, 5184.10, 5198.11, 5322.95, 5281.81, 5450.51];
  var fallbackCumInvest = [1000, 1500, 2500, 3000, 3200, 3400, 3800, 4000, 4000];
  var fallbackCumShares = [771.44, 1164.77, 1983.75, 2401.77, 2566.96, 2733.55, 3056.07, 3219.79, 3219.79];
  var fallbackMktValue = [1000.02, 1477.28, 2420.77, 2871.08, 3068.54, 3279.71, 3788.00, 3931.04, 4048.89];
  var fallbackPnl = [0.02, -22.72, -79.23, -128.92, -131.46, -120.29, -12.00, -68.96, 48.89];
  var fallbackCumReturn = [0.00, -1.51, -3.17, -4.30, -4.11, -3.54, -0.32, -1.72, 1.22];
  var fallbackNavValues = [1.2963, 1.2683, 1.2203, 1.1954, 1.1954, 1.1998, 1.2395, 1.2209, 1.2575];
  var fallbackAvgCost = [1.2963, 1.2878, 1.2602, 1.2491, 1.2466, 1.2438, 1.2434, 1.2423, 1.2423];

  function formatDate(d) {
    if (!d) return '';
    var s = String(d);
    if (/^\d{8}$/.test(s)) return s.substring(4, 6) + '-' + s.substring(6, 8);
    if (/^\d{4}-\d{2}-\d{2}$/.test(s)) return s.substring(5);
    return s;
  }

  function formatNumber(value, digits) {
    if (value == null || value === '' || isNaN(Number(value))) return '--';
    return Number(value).toLocaleString(undefined, {
      minimumFractionDigits: digits,
      maximumFractionDigits: digits
    });
  }

  function axisTooltip(unitMap, digitMap) {
    return {
      show: true,
      trigger: 'axis',
      appendToBody: true,
      axisPointer: { type: 'cross', lineStyle: { color: muted, type: 'dashed' }, label: { show: true } },
      backgroundColor: 'rgba(255,255,255,0.96)',
      borderColor: rule,
      borderWidth: 1,
      textStyle: { color: ink, fontSize: 12 },
      extraCssText: 'box-shadow:0 8px 24px rgba(15,23,42,.12);border-radius:8px;padding:8px 10px;z-index:99999;',
      formatter: function(params) {
        if (!params || !params.length) return '';
        var lines = ['<div style="font-weight:700;margin-bottom:4px;">' + params[0].axisValue + '</div>'];
        params.forEach(function(p) {
          var unit = unitMap && unitMap[p.seriesName] ? unitMap[p.seriesName] : '';
          var digits = digitMap && digitMap[p.seriesName] != null ? digitMap[p.seriesName] : 2;
          var value = formatNumber(p.value, digits);
          lines.push(
            '<div style="display:flex;align-items:center;gap:6px;white-space:nowrap;">' +
              '<span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:' + p.color + ';"></span>' +
              '<span>' + p.seriesName + '：</span>' +
              '<strong>' + value + unit + '</strong>' +
            '</div>'
          );
        });
        return lines.join('');
      }
    };
  }

  function extractArray(records, key, fallback) {
    return records.length ? records.map(function(r) { return r[key] != null ? r[key] : 0; }) : fallback;
  }

  function initCharts(data) {
    var records = [];
    var strategy = {};
    var valuation = {};
    var bond = {};
    var technical = {};
    var meta = {};
    var publicHistory = {};
    var valuationHistory = {};
    var bondHistory = {};
    var technicalHistory = {};
    var spreadHistory = {};

    if (data) {
      records = data.feishu_records || [];
      strategy = data.strategy_advice || {};
      valuation = data.index_valuation || {};
      bond = data.bond_yield || {};
      technical = data.technical || {};
      meta = data.meta || {};
      publicHistory = data.public_history || {};
      valuationHistory = data.index_valuation_history || {};
      bondHistory = data.bond_yield_history || {};
      technicalHistory = data.technical_history || {};
      spreadHistory = data.stock_bond_spread_history || {};
    }

    // ===== Time series from feishu_records =====
    var dates = records.length ? records.map(function(r) { return formatDate(r.date); }) : fallbackDates;
    var investments = extractArray(records, 'invest', fallbackInvestments);
    var publicIndexRows = (publicHistory.csi_dividend && publicHistory.csi_dividend.data) ? publicHistory.csi_dividend.data : [];
    var publicIndexByDate = {};
    publicIndexRows.forEach(function(row) { publicIndexByDate[row.record_date || row.date] = row.close; });
    var indexLevels = records.length ? records.map(function(r, i) {
      return publicIndexByDate[r.date] != null ? publicIndexByDate[r.date] : fallbackIndexLevels[i];
    }) : fallbackIndexLevels;
    var cumInvest = extractArray(records, 'cum_invest', fallbackCumInvest);
    var cumShares = extractArray(records, 'cum_shares', fallbackCumShares);
    var mktValue = extractArray(records, 'mkt_value', fallbackMktValue);
    var pnl = extractArray(records, 'pnl', fallbackPnl);
    var cumReturn = extractArray(records, 'cum_return_pct', fallbackCumReturn);
    var navValues = extractArray(records, 'nav', fallbackNavValues);
    var avgCost = extractArray(records, 'avg_cost', fallbackAvgCost);
    var valuationRows = (valuationHistory.csi_dividend && valuationHistory.csi_dividend.data) ? valuationHistory.csi_dividend.data : [];
    var spreadRows = (spreadHistory.csi_dividend && spreadHistory.csi_dividend.data) ? spreadHistory.csi_dividend.data : [];
    var rsiRows = (technicalHistory.csi_dividend && technicalHistory.csi_dividend.data) ? technicalHistory.csi_dividend.data : [];

    // ===== Gauge values from index_valuation & strategy_advice =====
    var csiDiv = valuation.csi_dividend || {};
    var peVal = csiDiv.pe2 != null ? csiDiv.pe2 : 10.66;
    var divYieldVal = csiDiv.div_yield2 != null ? csiDiv.div_yield2 : 4.47;
    var rsiVal = technical.rsi24 != null ? technical.rsi24 : 51.26;
    var spreadVal = strategy.spread != null ? strategy.spread : 2.73;

    // ===== Append public market data point for the display date =====
    var todayStr = meta.market_date || (csiDiv.date || (meta.update_time ? meta.update_time.split(' ')[0] : '2026-07-28'));
    var todayShort = todayStr.substring(5);
    var todayBond = bond && bond.y10 != null ? bond.y10 : 1.73;
    var todayIndex = (valuation.csi_dividend && valuation.csi_dividend.index_level) ? valuation.csi_dividend.index_level : (indexLevels.length ? indexLevels[indexLevels.length - 1] : 5450);
    // Use spot data for today's index level if available
    if (data && data.index_spot && data.index_spot.csi_dividend) {
      todayIndex = data.index_spot.csi_dividend.latest;
    }
    var lastRecord = records.length ? records[records.length - 1] : null;
    dates.push(todayShort);
    investments.push(0);
    indexLevels.push(todayIndex);
    cumInvest.push(lastRecord ? (lastRecord.cum_invest || 0) : 4000);
    cumShares.push(lastRecord ? (lastRecord.cum_shares || 0) : 3219);
    mktValue.push(lastRecord ? (lastRecord.mkt_value || 0) : 4048);
    pnl.push(lastRecord ? (lastRecord.pnl || 0) : 0);
    cumReturn.push(lastRecord ? (lastRecord.cum_return_pct || 0) : 0);
    navValues.push(lastRecord ? (lastRecord.nav || 0) : 1.25);
    avgCost.push(lastRecord ? (lastRecord.avg_cost || 0) : 1.24);

    // ===== Update KPI cards =====
    if (lastRecord) {
      document.getElementById('kpi-cum-invest').textContent = '\u00A5' + (lastRecord.cum_invest || 0).toLocaleString();
      document.getElementById('kpi-mkt-value').textContent = '\u00A5' + (lastRecord.mkt_value || 0).toLocaleString();
      var retPct = lastRecord.cum_return_pct || 0;
      var retEl = document.getElementById('kpi-cum-return');
      retEl.textContent = (retPct >= 0 ? '+' : '') + retPct + '%';
      retEl.className = 'kpi-value ' + (retPct >= 0 ? 'positive' : 'negative');
      document.getElementById('kpi-avg-cost').textContent = (lastRecord.avg_cost || 0).toFixed(4);
      document.getElementById('kpi-nav').textContent = (lastRecord.nav || 0).toFixed(4);
    }
    // Dynamically update records count
    var recordsInfoEl = document.getElementById('kpi-records-info');
    if (recordsInfoEl && records.length) {
      var firstD = String(records[0].date || '');
      var lastD = String(lastRecord.date || '');
      var firstYM = firstD.substring(0, 7).replace('-', '.');
      var lastYM = lastD.substring(0, 7).replace('-', '.');
      var lastM = lastD.substring(5, 7);
      var dateRange = (firstYM.substring(0, 4) === lastYM.substring(0, 4)) ? firstYM + '~' + lastM : firstYM + '~' + lastYM;
      recordsInfoEl.textContent = records.length + '笔记录 · ' + dateRange + ' · 飞书Base';
    }
    // PE & Dividend Yield from public API
    var peEl = document.getElementById('kpi-pe');
    peEl.textContent = peVal.toFixed(2);
    peEl.className = 'kpi-value ' + (peVal < 10.5 ? 'positive' : (peVal < 13 ? 'neutral' : 'negative'));
    var divEl = document.getElementById('kpi-div');
    divEl.textContent = divYieldVal.toFixed(2) + '%';
    divEl.className = 'kpi-value ' + (divYieldVal > 5 ? 'positive' : (divYieldVal > 3.5 ? 'neutral' : 'negative'));
    document.getElementById('kpi-pe-sub').textContent = '中证官网指数估值Excel · P/E2 · ' + (csiDiv.date || '2026-07-28');
    document.getElementById('kpi-div-sub').textContent = '中证官网指数估值Excel · D/P2 · ' + (csiDiv.date || '2026-07-28');

    // ===== Update meta info =====
    var metaUpdateEl = document.getElementById('meta-update');
    if (metaUpdateEl) metaUpdateEl.textContent = meta.update_time || '--';
    var metaPeriodEl = document.getElementById('meta-period');
    if (metaPeriodEl) metaPeriodEl.textContent = '2026.05~' + todayShort;
    var strategyTagEl = document.getElementById('strategy-tag');
    if (strategyTagEl) strategyTagEl.textContent = '数据驱动 · ' + (meta.period_label || '盘中') + '版';

    // ===== Update strategy advice cards =====
    document.getElementById('strat-composite-action').textContent = (strategy.composite_advice && strategy.composite_advice.action) ? strategy.composite_advice.action : '--';
    document.getElementById('strat-composite-detail').textContent = (strategy.composite_advice && strategy.composite_advice.detail) ? strategy.composite_advice.detail : '--';
    document.getElementById('strat-pe-action').textContent = (strategy.pe_advice && strategy.pe_advice.action) ? strategy.pe_advice.action : '--';
    document.getElementById('strat-pe-detail').textContent = (strategy.pe_advice && strategy.pe_advice.detail) ? strategy.pe_advice.detail : '--';
    document.getElementById('strat-spread-action').textContent = (strategy.spread_advice && strategy.spread_advice.action) ? strategy.spread_advice.action : '--';
    document.getElementById('strat-spread-detail').textContent = (strategy.spread_advice && strategy.spread_advice.detail) ? strategy.spread_advice.detail : '--';
    document.getElementById('strat-div-action').textContent = (strategy.div_advice && strategy.div_advice.action) ? strategy.div_advice.action : '--';
    document.getElementById('strat-div-detail').textContent = (strategy.div_advice && strategy.div_advice.detail) ? strategy.div_advice.detail : '--';
    document.getElementById('strat-rsi-action').textContent = (strategy.rsi_advice && strategy.rsi_advice.action) ? strategy.rsi_advice.action : '--';
    document.getElementById('strat-rsi-detail').textContent = (strategy.rsi_advice && strategy.rsi_advice.detail) ? strategy.rsi_advice.detail : '--';

    // Generate execution advice
    var execAdvice = '';
    var compAction = (strategy.composite_advice && strategy.composite_advice.action) ? strategy.composite_advice.action : '';
    if (compAction === '强力买入') {
      execAdvice = '建议按2倍基础金额进行定投，或考虑一次性狙击买入。多因子共振显示当前极具配置价值，可适度加大仓位。';
    } else if (compAction === '买入') {
      execAdvice = '建议按1.5倍基础金额进行定投。当前股债利差处于较高水平，估值合理偏低，适合分批布局积累份额。';
    } else if (compAction === '持有') {
      execAdvice = '维持基础定投金额，不增加也不减少。可继续持有现有仓位，密切关注PE分位和股债利差变化，等待信号。';
    } else if (compAction === '谨慎') {
      execAdvice = '建议减半定投金额或暂缓新增。当前PE2略高于低估阈值、RSI处于中性区间，但股债利差仍有吸引力，可保留现金等待更优买点。';
    } else if (compAction === '卖出') {
      execAdvice = '建议分批止盈，每次卖出20-30%仓位。当前估值已处于历史高位，落袋为安，锁定收益。';
    } else {
      execAdvice = '等待数据更新后生成操作建议。请关注每日08:00盘前版和14:30盘中版更新。';
    }
    document.getElementById('strat-execution').textContent = execAdvice;

    // ===== Strategy advice labels =====
    var peAdvice = (strategy.pe_advice && strategy.pe_advice.action) ? strategy.pe_advice.action : '合理偏高';
    var divAdvice = (strategy.div_advice && strategy.div_advice.action) ? strategy.div_advice.action : '正常区间';
    var spreadAdvice = (strategy.spread_advice && strategy.spread_advice.action) ? strategy.spread_advice.action : '低估·正常定投';
    var rsiAdvice = (strategy.rsi_advice && strategy.rsi_advice.action) ? strategy.rsi_advice.action : '正常区间';

    // ===== 10Y bond yield from JSON =====
    var bondData = [bond && bond.y10 != null ? bond.y10 : 1.725];

    var latestDate = records.length ? records[records.length - 1].date : (meta.update_time ? meta.update_time.split(' ')[0] : '2026-07-20');

    // ===== Chart 1: Investment Timeline =====
    var chart1 = echarts.init(document.getElementById('chart-investment-timeline'), null, { renderer: 'svg' });
    chart1.setOption({
      animation: false,
      tooltip: axisTooltip({ '定投金额': ' 元', '指数点位': ' 点' }, { '定投金额': 0, '指数点位': 2 }),
      legend: { data: ['定投金额', '指数点位'], textStyle: { color: muted, fontSize: 11 }, top: 0 },
      grid: commonGrid,
      xAxis: {
        type: 'category',
        data: dates,
        axisLabel: commonAxisLabel,
        axisLine: commonAxisLine
      },
      yAxis: [
        {
          type: 'value',
          name: '金额(¥)',
          position: 'left',
          axisLabel: commonAxisLabel,
          axisLine: commonAxisLine,
          splitLine: commonSplitLine
        },
        {
          type: 'value',
          name: '指数点位',
          position: 'right',
          min: 5000,
          max: 5800,
          axisLabel: commonAxisLabel,
          axisLine: commonAxisLine,
          splitLine: { show: false }
        }
      ],
      series: [
        {
          name: '定投金额',
          type: 'bar',
          yAxisIndex: 0,
          data: investments,
          itemStyle: {
            color: function(params) {
              return params.value > 0 ? accent : muted;
            },
            borderRadius: [3, 3, 0, 0]
          },
          barWidth: '40%'
        },
        {
          name: '指数点位',
          type: 'line',
          yAxisIndex: 1,
          data: indexLevels,
          smooth: true,
          symbol: 'circle',
          symbolSize: 7,
          lineStyle: { color: accent2, width: 2 },
          itemStyle: { color: accent2 },
          areaStyle: {
            color: {
              type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
              colorStops: [
                { offset: 0, color: 'rgba(212,163,115,0.15)' },
                { offset: 1, color: 'rgba(212,163,115,0)' }
              ]
            }
          }
        }
      ]
    });
    window.addEventListener('resize', function() { chart1.resize(); });

    // ===== Chart 2: Cumulative =====
    var chart2 = echarts.init(document.getElementById('chart-cumulative'), null, { renderer: 'svg' });
    chart2.setOption({
      animation: false,
      tooltip: axisTooltip({ '累计投入': ' 元', '持有市值': ' 元', '浮盈': ' 元' }, { '累计投入': 0, '持有市值': 2, '浮盈': 2 }),
      legend: { data: ['累计投入', '持有市值', '浮盈'], textStyle: { color: muted, fontSize: 11 }, top: 0 },
      grid: commonGrid,
      xAxis: {
        type: 'category',
        data: dates,
        axisLabel: commonAxisLabel,
        axisLine: commonAxisLine
      },
      yAxis: [
        {
          type: 'value',
          name: '金额(¥)',
          position: 'left',
          axisLabel: commonAxisLabel,
          axisLine: commonAxisLine,
          splitLine: commonSplitLine
        },
        {
          type: 'value',
          name: '浮盈(¥)',
          position: 'right',
          axisLabel: commonAxisLabel,
          axisLine: commonAxisLine,
          splitLine: { show: false }
        }
      ],
      series: [
        {
          name: '累计投入',
          type: 'line',
          yAxisIndex: 0,
          data: cumInvest,
          smooth: true,
          symbol: 'none',
          lineStyle: { color: accent, width: 2, type: 'dashed' },
          itemStyle: { color: accent },
          areaStyle: {
            color: {
              type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
              colorStops: [
                { offset: 0, color: 'rgba(82,183,136,0.2)' },
                { offset: 1, color: 'rgba(82,183,136,0)' }
              ]
            }
          }
        },
        {
          name: '持有市值',
          type: 'line',
          yAxisIndex: 0,
          data: mktValue,
          smooth: true,
          symbol: 'circle',
          symbolSize: 6,
          lineStyle: { color: accent2, width: 2 },
          itemStyle: { color: accent2 }
        },
        {
          name: '浮盈',
          type: 'bar',
          yAxisIndex: 1,
          data: pnl,
          itemStyle: {
            color: function(params) {
              return params.value >= 0 ? red : green;
            },
            borderRadius: [3, 3, 0, 0]
          },
          barWidth: '30%'
        }
      ]
    });
    window.addEventListener('resize', function() { chart2.resize(); });

    // ===== Gauge: PE =====
    var gaugePE = echarts.init(document.getElementById('gauge-pe'), null, { renderer: 'svg' });
    gaugePE.setOption({
      animation: false,
      tooltip: {
        show: true,
        formatter: '{b}: {c}'
      },
      series: [{
        type: 'gauge',
        min: 5,
        max: 18,
        splitNumber: 5,
        radius: '78%',
        center: ['50%', '42%'],
        progress: { show: true, width: 10 },
        axisLine: { lineStyle: { width: 10, color: [
          [0.2, green],
          [0.42, yellow],
          [0.72, accent2],
          [1, red]
        ]}},
        pointer: { width: 4, length: '60%' },
        axisTick: { distance: -10, length: 5, lineStyle: { color: muted } },
        splitLine: { distance: -12, length: 8, lineStyle: { color: muted, width: 1 } },
        axisLabel: { distance: -2, color: muted, fontSize: 9 },
        detail: {
          valueAnimation: true,
          formatter: '{value}',
          color: ink,
          fontSize: 22,
          fontWeight: 700,
          offsetCenter: [0, '28%']
        },
        title: { offsetCenter: [0, '52%'], color: muted, fontSize: 10 },
        data: [{ value: peVal, name: peAdvice }]
      }]
    });
    window.addEventListener('resize', function() { gaugePE.resize(); });

    // ===== Gauge: Dividend Yield =====
    var gaugeDiv = echarts.init(document.getElementById('gauge-dividend'), null, { renderer: 'svg' });
    gaugeDiv.setOption({
      animation: false,
      tooltip: {
        show: true,
        formatter: '{b}: {c}%'
      },
      series: [{
        type: 'gauge',
        min: 0,
        max: 8,
        splitNumber: 4,
        radius: '78%',
        center: ['50%', '42%'],
        progress: { show: true, width: 10 },
        axisLine: { lineStyle: { width: 10, color: [
          [0.3, red],
          [0.43, yellow],
          [0.72, accent2],
          [1, green]
        ]}},
        pointer: { width: 4, length: '60%' },
        axisTick: { distance: -10, length: 5, lineStyle: { color: muted } },
        splitLine: { distance: -12, length: 8, lineStyle: { color: muted, width: 1 } },
        axisLabel: { distance: -2, color: muted, fontSize: 9 },
        detail: {
          valueAnimation: true,
          formatter: '{value}%',
          color: ink,
          fontSize: 22,
          fontWeight: 700,
          offsetCenter: [0, '28%']
        },
        title: { offsetCenter: [0, '52%'], color: muted, fontSize: 10 },
        data: [{ value: divYieldVal, name: divAdvice }]
      }]
    });
    window.addEventListener('resize', function() { gaugeDiv.resize(); });

    // ===== Gauge: Stock-Bond Spread =====
    var gaugeSpread = echarts.init(document.getElementById('gauge-spread'), null, { renderer: 'svg' });
    gaugeSpread.setOption({
      animation: false,
      tooltip: {
        show: true,
        formatter: '{b}: {c}%'
      },
      series: [{
        type: 'gauge',
        min: 0,
        max: 5,
        splitNumber: 5,
        radius: '78%',
        center: ['50%', '42%'],
        progress: { show: true, width: 10 },
        axisLine: { lineStyle: { width: 10, color: [
          [0.4, red],
          [0.5, yellow],
          [0.7, accent2],
          [1, green]
        ]}},
        pointer: { width: 4, length: '60%' },
        axisTick: { distance: -10, length: 5, lineStyle: { color: muted } },
        splitLine: { distance: -12, length: 8, lineStyle: { color: muted, width: 1 } },
        axisLabel: { distance: -2, color: muted, fontSize: 9 },
        detail: {
          valueAnimation: true,
          formatter: '{value}%',
          color: ink,
          fontSize: 22,
          fontWeight: 700,
          offsetCenter: [0, '28%']
        },
        title: { offsetCenter: [0, '52%'], color: muted, fontSize: 10 },
        data: [{ value: spreadVal, name: spreadAdvice }]
      }]
    });
    window.addEventListener('resize', function() { gaugeSpread.resize(); });

    // ===== Gauge: RSI =====
    var gaugeRSI = echarts.init(document.getElementById('gauge-rsi'), null, { renderer: 'svg' });
    gaugeRSI.setOption({
      animation: false,
      tooltip: {
        show: true,
        formatter: '{b}: {c}'
      },
      series: [{
        type: 'gauge',
        min: 0,
        max: 100,
        splitNumber: 10,
        radius: '78%',
        center: ['50%', '42%'],
        progress: { show: true, width: 10 },
        axisLine: { lineStyle: { width: 10, color: [
          [0.3, green],
          [0.7, accent2],
          [1, red]
        ]}},
        pointer: { width: 4, length: '60%' },
        axisTick: { distance: -10, length: 5, lineStyle: { color: muted } },
        splitLine: { distance: -12, length: 8, lineStyle: { color: muted, width: 1 } },
        axisLabel: { distance: -2, color: muted, fontSize: 9 },
        detail: {
          valueAnimation: true,
          formatter: '{value}',
          color: ink,
          fontSize: 22,
          fontWeight: 700,
          offsetCenter: [0, '28%']
        },
        title: { offsetCenter: [0, '52%'], color: muted, fontSize: 10 },
        data: [{ value: rsiVal, name: rsiAdvice }]
      }]
    });
    window.addEventListener('resize', function() { gaugeRSI.resize(); });

    // ===== Chart: PE2 & D/P2 Daily Trend =====
    var peDivRows = valuationRows.length ? valuationRows : [{ date: todayStr, pe2: peVal, div_yield2: divYieldVal }];
    var peDivDates = peDivRows.map(function(row) { return formatDate(row.date); });
    var pe2Series = peDivRows.map(function(row) { return row.pe2; });
    var div2Series = peDivRows.map(function(row) { return row.div_yield2; });
    var chartPEDiv = echarts.init(document.getElementById('chart-pe-div-trend'), null, { renderer: 'svg' });
    chartPEDiv.setOption({
      animation: false,
      tooltip: axisTooltip({ 'P/E2': '', 'D/P2': '%' }, { 'P/E2': 2, 'D/P2': 2 }),
      legend: { data: ['P/E2', 'D/P2'], textStyle: { color: muted, fontSize: 11 }, top: 0 },
      grid: commonGrid,
      xAxis: { type: 'category', data: peDivDates, axisLabel: commonAxisLabel, axisLine: commonAxisLine },
      yAxis: [
        { type: 'value', name: 'P/E2', position: 'left', min: 9, max: 12, axisLabel: commonAxisLabel, axisLine: commonAxisLine, splitLine: commonSplitLine },
        { type: 'value', name: 'D/P2(%)', position: 'right', min: 4, max: 6, axisLabel: { color: muted, fontSize: 11, formatter: '{value}%' }, axisLine: commonAxisLine, splitLine: { show: false } }
      ],
      series: [
        {
          name: 'P/E2',
          type: 'line',
          yAxisIndex: 0,
          data: pe2Series,
          smooth: true,
          symbol: 'circle',
          symbolSize: 5,
          lineStyle: { color: accent, width: 2 },
          itemStyle: { color: accent }
        },
        {
          name: 'D/P2',
          type: 'line',
          yAxisIndex: 1,
          data: div2Series,
          smooth: true,
          symbol: 'circle',
          symbolSize: 5,
          lineStyle: { color: accent2, width: 2 },
          itemStyle: { color: accent2 }
        }
      ]
    });
    window.addEventListener('resize', function() { chartPEDiv.resize(); });

    // ===== Chart: Stock-Bond Spread Daily Trend =====
    var stockBondRows = spreadRows.length ? spreadRows : [{ date: todayStr, div_yield2: divYieldVal, y10: todayBond, spread: spreadVal }];
    var stockBondDates = stockBondRows.map(function(row) { return formatDate(row.date); });
    var stockBondDiv = stockBondRows.map(function(row) { return row.div_yield2; });
    var stockBondYield = stockBondRows.map(function(row) { return row.y10; });
    var stockBondSpread = stockBondRows.map(function(row) { return row.spread; });
    var chartSB = echarts.init(document.getElementById('chart-stock-bond'), null, { renderer: 'svg' });
    chartSB.setOption({
      animation: false,
      tooltip: axisTooltip({ 'D/P2': '%', '10年期国债': '%', '股债利差': '%' }, { 'D/P2': 2, '10年期国债': 3, '股债利差': 2 }),
      legend: { data: ['D/P2', '10年期国债', '股债利差'], textStyle: { color: muted, fontSize: 11 }, top: 0 },
      grid: commonGrid,
      xAxis: { type: 'category', data: stockBondDates, axisLabel: commonAxisLabel, axisLine: commonAxisLine },
      yAxis: [
        { type: 'value', name: '收益率(%)', position: 'left', min: 0, max: 6, axisLabel: { color: muted, fontSize: 11, formatter: '{value}%' }, axisLine: commonAxisLine, splitLine: commonSplitLine },
        { type: 'value', name: '利差(%)', position: 'right', min: 0, max: 4, axisLabel: { color: muted, fontSize: 11, formatter: '{value}%' }, axisLine: commonAxisLine, splitLine: { show: false } }
      ],
      series: [
        { name: 'D/P2', type: 'line', yAxisIndex: 0, data: stockBondDiv, smooth: true, symbol: 'circle', symbolSize: 5, lineStyle: { color: accent, width: 2 }, itemStyle: { color: accent } },
        { name: '10年期国债', type: 'line', yAxisIndex: 0, data: stockBondYield, smooth: true, symbol: 'circle', symbolSize: 5, lineStyle: { color: muted, width: 2 }, itemStyle: { color: muted } },
        { name: '股债利差', type: 'bar', yAxisIndex: 1, data: stockBondSpread, itemStyle: { color: accent2, borderRadius: [3, 3, 0, 0] }, barWidth: '35%' }
      ]
    });
    window.addEventListener('resize', function() { chartSB.resize(); });

    // ===== Chart: RSI24 Daily Trend =====
    var rsiTrendRows = rsiRows.length ? rsiRows : [{ date: todayStr, rsi24: rsiVal }];
    var rsiTrendDates = rsiTrendRows.map(function(row) { return formatDate(row.date); });
    var rsiTrendValues = rsiTrendRows.map(function(row) { return row.rsi24; });
    var chartRSI = echarts.init(document.getElementById('chart-rsi-detail'), null, { renderer: 'svg' });
    chartRSI.setOption({
      animation: false,
      tooltip: axisTooltip({ 'RSI24': '' }, { 'RSI24': 2 }),
      grid: commonGrid,
      xAxis: { type: 'category', data: rsiTrendDates, axisLabel: commonAxisLabel, axisLine: commonAxisLine },
      yAxis: { type: 'value', name: 'RSI24', min: 0, max: 100, axisLabel: commonAxisLabel, axisLine: commonAxisLine, splitLine: commonSplitLine },
      series: [{
        name: 'RSI24',
        type: 'line',
        data: rsiTrendValues,
        smooth: true,
        symbol: 'circle',
        symbolSize: 5,
        lineStyle: { color: purple, width: 2 },
        itemStyle: { color: purple },
        markLine: {
          silent: true,
          symbol: 'none',
          lineStyle: { type: 'dashed', opacity: 0.5 },
          data: [
            { yAxis: 30, lineStyle: { color: green }, label: { formatter: '超卖 30', color: green, fontSize: 10 } },
            { yAxis: 70, lineStyle: { color: red }, label: { formatter: '超买 70', color: red, fontSize: 10 } },
            { yAxis: 50, lineStyle: { color: yellow }, label: { formatter: '中性 50', color: yellow, fontSize: 10 } }
          ]
        }
      }]
    });
    window.addEventListener('resize', function() { chartRSI.resize(); });

  }

  // Use inline data if available (for self-contained/shared HTML), otherwise fetch from file
  if (typeof window.__MARKET_DATA__ !== 'undefined' && window.__MARKET_DATA__) {
    initCharts(window.__MARKET_DATA__);
  } else {
    fetch('./assets/market_data.json')
      .then(function(response) { return response.json(); })
      .then(function(data) { initCharts(data); })
      .catch(function(err) {
        console.error('Failed to load market_data.json, using fallback data', err);
        initCharts(null);
      });
  }
})();
