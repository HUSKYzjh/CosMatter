import { For, Show, createSignal, createUniqueId } from "solid-js";
import { CalculationError, calculateFieldResponse, countPstOccupations } from "../../plugins/dsh-cosmatter-research-plugin/src/material-calculations";
import type { UiLocale } from "./fleetRegistry";
import { ActionButton } from "./uiPrimitives";
import "./material-calculation.css";

type Props = { locale: UiLocale };
type Problem = { field: string; zh: string; en: string };
const label = (locale: UiLocale, zh: string, en: string) => locale === "zh" ? zh : en;

export function OccupancyCalculator(props: Props) {
  const x = (zh: string, en: string) => label(props.locale, zh, en);
  const [result, setResult] = createSignal<ReturnType<typeof countPstOccupations>>();
  const [invalid, setInvalid] = createSignal(false);
  const errorId = createUniqueId();
  let input!: HTMLInputElement;
  function compute() {
    try {
      setResult(countPstOccupations(input.value));
      setInvalid(false);
    } catch (error) {
      if (!(error instanceof CalculationError)) throw error;
      setResult(undefined);
      setInvalid(true);
      input.focus();
    }
  }
  return <form class="material-calculation" aria-label={x("Pb/Sr 占位计算", "Pb/Sr occupancy calculator")}
    onSubmit={event => { event.preventDefault(); compute(); }}>
    <p>{x("在浏览器中计算 (PbₓSr₁₋ₓ)TiO₃ 的 8×8×8 超胞，共 512 个 A 位。", "Count occupations locally for the 512 A sites in an 8×8×8 (PbₓSr₁₋ₓ)TiO₃ supercell.")}</p>
    <label>{x("Pb 占 A 位的分数 x", "Pb fraction of A sites, x")}
      <input ref={input} name="pb_fraction" value="0.5" maxLength={256} autocomplete="off" spellcheck={false}
        aria-invalid={invalid()} aria-describedby={invalid() ? errorId : undefined}
        onInput={() => { setResult(undefined); setInvalid(false); }} />
    </label>
    <ActionButton type="submit" size="sm">{x("计算占位数", "Calculate occupations")}</ActionButton>
    <Show when={invalid()}><p id={errorId} role="alert">{x("请输入 0 到 1 的精确小数或分数，例如 0.5 或 1/3。分母必须大于零。", "Enter an exact decimal or fraction from 0 to 1, such as 0.5 or 1/3, with a positive denominator.")}</p></Show>
    <div aria-live="polite" aria-atomic="true">
      <Show when={result()} keyed>{value => value.realizable
        ? <div class="material-result">
          <strong>{value.n_pb} Pb · {value.n_sr} Sr</strong>
          <span>{x("带编号的 A 位排列数（对称性去重前）", "Labeled A-site arrangements before symmetry reduction")}</span>
          <code>{value.arrangement_count}</code>
        </div>
        : <div class="material-result">
          <strong>{x("512 个 A 位无法精确实现这个组分", "This composition cannot be represented on 512 A sites")}</strong>
          <span>{x("选择相邻的整数组分继续计算。", "Choose a neighboring composition to count its arrangements.")}</span>
          <div class="material-neighbors"><For each={value.nearest_compositions}>{item =>
            <ActionButton size="sm" onClick={() => { input.value = item.pb_fraction; compute(); input.focus(); }}>
              {item.n_pb} Pb · {item.n_sr} Sr <span>(x = {item.pb_fraction})</span>
            </ActionButton>
          }</For></div>
        </div>
      }</Show>
    </div>
  </form>;
}

export function FieldResponseCalculator(props: Props) {
  const x = (zh: string, en: string) => label(props.locale, zh, en);
  const [observable, setObservable] = createSignal("normal_strain");
  const [result, setResult] = createSignal<ReturnType<typeof calculateFieldResponse>>();
  const [error, setError] = createSignal<Problem>();
  const errorId = createUniqueId();
  let minus!: HTMLInputElement;
  let plus!: HTMLInputElement;
  const unit = () => observable() === "normal_strain" ? x("无量纲应变", "fractional strain") : "C/m²";
  function clear() { setResult(undefined); setError(undefined); }
  function compute(form: HTMLFormElement) {
    clear();
    const data = new FormData(form);
    const field = (name: string) => String(data.get(name) ?? "").trim();
    const fail = (problem: Problem) => {
      setError(problem);
      (form.elements.namedItem(problem.field) as HTMLElement | null)?.focus();
    };
    const numbers: number[] = [];
    for (const [name, zh, en] of [["field", "场强幅值", "field magnitude"], ["minus", "负电场均值", "mean at −E"], ["plus", "正电场均值", "mean at +E"]]) {
      const raw = field(name);
      const value = Number(raw);
      if (!/^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:e[+-]?\d+)?$/i.test(raw) || !Number.isFinite(value)) {
        return fail({ field: name, zh: `请为“${zh}”输入有限数值，可使用科学计数法。`, en: `Enter a finite number for ${en}. Scientific notation is supported.` });
      }
      numbers.push(value);
    }
    try {
      setResult(calculateFieldResponse({
        axis: field("axis"), mechanical_boundary: field("boundary"), observable: observable(),
        field_magnitude_V_per_m: numbers[0], mean_at_minus_field: numbers[1], mean_at_plus_field: numbers[2],
      }));
    } catch (cause) {
      if (!(cause instanceof CalculationError)) throw cause;
      if (cause.code === "clamped_strain") return fail({ field: "boundary", zh: "逆压电系数需要应变自由弛豫，请选固定应力并使用该边界下的均值。", en: "For a converse piezoelectric coefficient, choose fixed stress and supply means measured with free strain." });
      if (cause.code === "finite_fields") return fail({ field: "field", zh: "请输入大于零的场强幅值，单位为 V/m。", en: "Enter a positive field magnitude in V/m." });
      fail({ field: "field", zh: "结果超出可表示范围，请核对场强、均值及其单位。", en: cause.message });
    }
  }
  const problem = (name: string) => error()?.field === name;
  return <form class="material-calculation" aria-label={x("MD 电场响应计算", "MD field-response calculator")}
    onInput={clear} onChange={clear} onSubmit={event => { event.preventDefault(); compute(event.currentTarget); }}>
    <p>{x("计算仅使用本页输入的均值。取同温、同极化分支在 ±E 下的平衡值，应变用小数表示。", "This calculation uses the means entered here. Use equilibrated values at ±E on the same polarization branch and at the same temperature. Enter strain as a fraction.")}</p>
    <div class="material-inputs">
      <label>{x("计算目标", "Response")}
        <select name="observable" value={observable()} onChange={event => {
          setObservable(event.currentTarget.value); minus.value = ""; plus.value = "";
        }}>
          <option value="normal_strain">{x("纵向逆压电系数", "Longitudinal converse piezoelectric coefficient")}</option>
          <option value="polarization_C_per_m2">{x("纵向相对介电常数", "Longitudinal relative permittivity")}</option>
        </select></label>
      <label>{x("场与测量轴", "Field and measurement axis")}<select name="axis"><option>x</option><option>y</option><option selected>z</option></select></label>
      <label>{x("力学边界", "Mechanical boundary")}<select name="boundary" aria-invalid={problem("boundary")} aria-describedby={problem("boundary") ? errorId : undefined}>
        <option value="fixed_stress">{x("固定应力", "Fixed stress")}</option><option value="fixed_strain">{x("固定应变", "Fixed strain")}</option>
      </select></label>
      <label>{x("场强幅值 E（V/m）", "Field magnitude E (V/m)")}<input name="field" placeholder="1e6" inputmode="decimal"
        aria-invalid={problem("field")} aria-describedby={problem("field") ? errorId : undefined} /></label>
      <label>{x("负电场均值", "Mean at −E")} ({unit()})<input ref={minus} name="minus" inputmode="decimal"
        aria-invalid={problem("minus")} aria-describedby={problem("minus") ? errorId : undefined} /></label>
      <label>{x("正电场均值", "Mean at +E")} ({unit()})<input ref={plus} name="plus" inputmode="decimal"
        aria-invalid={problem("plus")} aria-describedby={problem("plus") ? errorId : undefined} /></label>
    </div>
    <ActionButton type="submit" size="sm">{x("计算场响应", "Calculate field response")}</ActionButton>
    <Show when={error()}>{problem => <p id={errorId} role="alert">{x(problem().zh, problem().en)}</p>}</Show>
    <div aria-live="polite" aria-atomic="true"><Show when={result()}>{value =>
      <div class="material-result"><strong>{value().component} = {value().value} {value().unit === "1" ? x("（无量纲）", "(dimensionless)") : value().unit}</strong>
        <code>{value().formula}</code><span>{x("此值由输入均值作中心差分得到。可用独立轨迹和多个场强检查不确定度与线性。", "Central difference from the supplied means. Use independent trajectories and field magnitudes to assess uncertainty and linearity.")}</span>
      </div>
    }</Show></div>
  </form>;
}
