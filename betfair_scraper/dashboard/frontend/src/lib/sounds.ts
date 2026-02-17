const STORAGE_KEY = "furbo-sound-enabled"

let audioCtx: AudioContext | null = null

function getAudioContext(): AudioContext {
  if (!audioCtx) {
    audioCtx = new AudioContext()
  }
  return audioCtx
}

export function isSoundEnabled(): boolean {
  return localStorage.getItem(STORAGE_KEY) !== "false"
}

export function setSoundEnabled(enabled: boolean) {
  localStorage.setItem(STORAGE_KEY, String(enabled))
}

/** Bell-like alert for new betting signals. */
export function playSignalAlert() {
  if (!isSoundEnabled()) return

  try {
    const ctx = getAudioContext()
    if (ctx.state === "suspended") {
      ctx.resume()
    }

    const now = ctx.currentTime
    const baseFreq = 800 // Base frequency (bell fundamental)
    const duration = 1.2 // Bell ring duration

    // Bell harmonics: fundamental + overtones
    const harmonics = [
      { freq: baseFreq, vol: 0.25 },           // Fundamental
      { freq: baseFreq * 2.4, vol: 0.15 },     // 2nd partial (slightly inharmonic)
      { freq: baseFreq * 3.8, vol: 0.08 },     // 3rd partial
      { freq: baseFreq * 5.2, vol: 0.04 },     // 4th partial
    ]

    harmonics.forEach(({ freq, vol }) => {
      const osc = ctx.createOscillator()
      const gain = ctx.createGain()

      osc.type = "sine"
      osc.frequency.value = freq

      // Bell envelope: sharp attack, exponential decay
      gain.gain.setValueAtTime(vol, now)
      gain.gain.exponentialRampToValueAtTime(0.001, now + duration)

      osc.connect(gain).connect(ctx.destination)
      osc.start(now)
      osc.stop(now + duration)
    })
  } catch {
    // Audio not available — silently ignore
  }
}
