// fake backend so the window runs without goggles
// index.html?state=idle|unplugged|nodriver|noscreen|untested|waiting|streaming|error holds one state, state=fresh is a first run,
// state=update offers a newer release. Add &mac to see the Mac window
(() => {
  'use strict';
  const params = new URLSearchParams(location.search), frozen = params.get('state'), mac = params.has('mac');
  const displays = [
    { index: 0, name: 'Display 1', x: 0, y: 0, width: 2560, height: 1600, hz: 240, primary: true },
    { index: 1, name: 'Display 2', x: 2560, y: 260, width: 1920, height: 1080, hz: 60, primary: false },
  ];
  const bitrates = {
    60: { allowed: [8, 10, 12, 16, 20, 24], auto: 24 }, 75: { allowed: [8, 10, 12, 16, 20, 24, 30], auto: 30 },
    90: { allowed: [8, 10, 12, 16, 20, 24, 30, 32], auto: 32 }, 100: { allowed: [8, 10, 12, 16, 20, 24, 30, 32, 40], auto: 32 },
  };
  const tested_versions = ['01.11.00.00', '01.14.00.00'];
  const device = frozen === 'untested'
    ? { model: 'DJI Goggles 2', identity: 'E3T ZV900 AC Feb 26 2025|12:39:57', build: 'Feb 26 2025', version: null, tested: false, tested_versions }
    : { model: 'DJI Goggles 2', identity: 'E3T ZV900 AC Dec 24 2024|12:34:04', build: 'Dec 24 2024', version: '01.11.00.00', tested: true, tested_versions };
  const state = {
    app: { name: 'Goggles Bridge', version: '0.1.0', platform: mac ? 'darwin' : 'win32', updatable: true },
    checks: { driver: { needed: !mac, ok: mac || frozen !== 'nodriver' }, screen: { needed: mac, ok: !mac || frozen !== 'noscreen' },
      ffmpeg: { needed: !mac, ok: true },
      attached: !['unplugged', 'fresh'].includes(frozen) },
    displays,
    options: { fps: 100, bitrate_mbps: null, capture: 'gfxcapture', display_index: 0, show_cursor: true, preset: 'p1',
      keyframe_seconds: 3, low_latency: true, usb_write_size: 16384, h264_profile: 'high', adaptive_quant: false },
    choices: { fps: [60, 75, 90, 100], capture: ['gfxcapture', 'ddagrab'], preset: ['p1', 'p4'], keyframe_seconds: [1, 3],
      h264_profile: ['baseline', 'high'], usb_write_size: [2048, 16384], bitrates },
    frame_limit: 56000, phase: 'idle', problem: null, device: ['unplugged', 'fresh', 'nodriver', 'noscreen'].includes(frozen) ? null : device,
    stats: null, oversize: 0, log: null,
    onboarded: frozen !== 'fresh',
  };
  let timers = [], ticker;

  const tick = () => { state.stats = { fps: state.options.fps - Math.random(), send_ms_p95: .6 + Math.random() * .2, frame_bytes_max: 41000 + Math.random() * 4000 }; };
  function stream() {
    Object.assign(state, { phase: 'streaming', problem: null, device });
    tick();
    ticker = setInterval(tick, 5000);
  }
  function halt() {
    timers.forEach(clearTimeout);
    clearInterval(ticker);
    timers = [];
  }
  const after = (ms, change) => timers.push(setTimeout(change, ms));

  if (frozen === 'fresh') setTimeout(() => { state.checks.attached = true; state.device = device; }, 9000);
  else if (frozen === 'streaming') stream();
  else if (frozen === 'waiting') Object.assign(state, { phase: 'waiting', problem: { code: 'virtual_flight', message: '' } });
  else if (frozen === 'error') Object.assign(state, { phase: 'error', device, problem: { code: 'rejected', message: 'Goggles rejected 0b/1a: d6' } });

  window.demoBackend = {
    snapshot: async () => JSON.parse(JSON.stringify(state)),
    set_options: async options => {
      const next = { ...state.options, ...options };
      if (next.bitrate_mbps !== null && !bitrates[next.fps].allowed.includes(next.bitrate_mbps)) {
        return { error: `At ${next.fps} fps, use at most ${bitrates[next.fps].allowed.at(-1)} Mbps.` };
      }
      state.options = next;
      return { ok: true };
    },
    start: async () => {
      halt();
      Object.assign(state, { phase: 'checking', problem: null, stats: null });
      after(700, () => Object.assign(state, { phase: 'waiting', problem: { code: 'virtual_flight', message: '' } }));
      after(3600, () => Object.assign(state, { phase: 'connecting', problem: null }));
      after(4100, () => Object.assign(state, { phase: 'ready', device }));
      after(4700, stream);
      return { ok: true };
    },
    stop: async () => {
      halt();
      Object.assign(state, { phase: 'idle', problem: null, stats: null });
      return { ok: true };
    },
    finish_setup: async () => { state.onboarded = true; return { ok: true }; },
    diagnostics: async () => 'Goggles Bridge demo',
    open_link: async () => ({ ok: true }),
    check_update: async () => ({ version: frozen === 'update' ? '0.2.0' : null }),
    install_update: () => new Promise(done => setTimeout(() => done({ error: "Couldn't install the update" }), 3000)),
  };
})();
