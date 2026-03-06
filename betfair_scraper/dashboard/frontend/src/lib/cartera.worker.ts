/**
 * Web Worker para Phase 1 del preset optimizer.
 * Recibe un subconjunto de drawOpts y evalúa todas las combinaciones
 * en un hilo separado, sin bloquear el hilo principal de React.
 *
 * IMPORTANTE: onmessage es async y cede el hilo cada YIELD_EVERY iteraciones
 * mediante await setTimeout(0). Esto evita que Chrome mate el proceso del
 * renderer al detectar saturación continua de CPU (RESULT_CODE_HUNG).
 */
import { evaluateCombo } from './cartera'
import type {
  CarteraBet, VersionCombo, RiskFilter, BankrollMode, PresetKey,
  DrawVersion, XGCarteraVersion, DriftCarteraVersion, ClusteringCarteraVersion,
  PressureCarteraVersion, TardeAsiaVersion, MomentumXGVersion,
  LayOver15CarteraVersion, LayDrawAsymVersion, LayOver25DefVersion,
  BackSotDomVersion, BackOver15EarlyVersion, LayFalseFavVersion,
} from './cartera'

const YIELD_EVERY = 20000
const _yield = () => new Promise<void>(r => setTimeout(r, 0))

interface WorkerInput {
  bets: CarteraBet[]
  bankrollInit: number
  criterion: Exclude<PresetKey, null>
  drawSubset: DrawVersion[]
  xgOpts: XGCarteraVersion[]
  driftOpts: DriftCarteraVersion[]
  clusteringOpts: ClusteringCarteraVersion[]
  pressureOpts: PressureCarteraVersion[]
  tardeAsiaOpts: TardeAsiaVersion[]
  momentumXGOpts: MomentumXGVersion[]
  layOver15Opts: LayOver15CarteraVersion[]
  layDrawAsymOpts: LayDrawAsymVersion[]
  layOver25DefOpts: LayOver25DefVersion[]
  backSotDomOpts: BackSotDomVersion[]
  backOver15EarlyOpts: BackOver15EarlyVersion[]
  layFalseFavOpts: LayFalseFavVersion[]
  brOpts: BankrollMode[]
  riskOpts: RiskFilter[]
}

self.onmessage = async ({ data }: MessageEvent<WorkerInput>) => {
  const {
    bets, bankrollInit, criterion, drawSubset,
    xgOpts, driftOpts, clusteringOpts, pressureOpts, tardeAsiaOpts,
    momentumXGOpts, layOver15Opts, layDrawAsymOpts, layOver25DefOpts,
    backSotDomOpts, backOver15EarlyOpts, layFalseFavOpts, brOpts, riskOpts,
  } = data

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const scoreOf = (result: any): number => {
    switch (criterion) {
      case "max_roi": return result.flatRoi
      case "max_pl":  return result.flatPl
      case "max_wr":  return result.winPct + result.total * 0.01
      case "min_dd":  return result.managedPl - result.managedMaxDd.maxDd * 2 + result.winPct * 0.5
      default:        return result.flatPl
    }
  }

  const total =
    drawSubset.length * xgOpts.length * driftOpts.length * clusteringOpts.length *
    pressureOpts.length * tardeAsiaOpts.length * momentumXGOpts.length * layOver15Opts.length *
    layDrawAsymOpts.length * layOver25DefOpts.length * backSotDomOpts.length *
    backOver15EarlyOpts.length * layFalseFavOpts.length * brOpts.length * riskOpts.length

  let bestCombo: VersionCombo | null = null
  let bestRisk: RiskFilter = "all"
  let bestScore = -Infinity
  let itr = 0

  for (const draw of drawSubset)
  for (const xg of xgOpts)
  for (const drift of driftOpts)
  for (const clustering of clusteringOpts)
  for (const pressure of pressureOpts)
  for (const tardeAsia of tardeAsiaOpts)
  for (const momentumXG of momentumXGOpts)
  for (const layOver15 of layOver15Opts)
  for (const layDrawAsym of layDrawAsymOpts)
  for (const layOver25Def of layOver25DefOpts)
  for (const backSotDom of backSotDomOpts)
  for (const backOver15Early of backOver15EarlyOpts)
  for (const layFalseFav of layFalseFavOpts)
  for (const br of brOpts)
  for (const risk of riskOpts) {
    const combo: VersionCombo = { draw, xg, drift, clustering, pressure, tardeAsia, momentumXG, layOver15, layDrawAsym, layOver25Def, backSotDom, backOver15Early, layFalseFav, br }
    const result = evaluateCombo(bets, combo, bankrollInit, risk)
    if (result && result.total >= 3) {
      const score = scoreOf(result)
      if (score > bestScore) { bestScore = score; bestCombo = combo; bestRisk = risk }
    }
    if (++itr % YIELD_EVERY === 0) {
      self.postMessage({ type: 'progress', itr, total })
      await _yield()  // cede el hilo del worker para que Chrome pueda respirar
    }
  }

  self.postMessage({ type: 'done', bestCombo, bestRisk, bestScore })
}
