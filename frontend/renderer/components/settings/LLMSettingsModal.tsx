import { t, localizeMessage } from '../../i18n';
import { useEffect, useRef, useState } from 'react';
import { sspClient } from '../../services/ssp_client';
import './LLMSettingsModal.css';

interface Profile {
  id: string; name: string; provider: string; model: string; api_base_url: string;
  vendor?: string;
  has_api_key: boolean; timeout_seconds: number; temperature: number; max_output_tokens: number | null;
}
interface Draft {
  id?: string; name: string; provider: string; model: string; api_base_url: string;
  vendor: string;
  api_key: string; clear_api_key: boolean; timeout_seconds: number; temperature: number; max_output_tokens: number;
}
interface Preset { id: string; name: string; provider: string; api_base_url: string; models: string[]; source_url: string; note: string }
const empty = (): Draft => ({ vendor: 'custom', name: '', provider: 'openai_compatible', model: '', api_base_url: '', api_key: '',
  clear_api_key: false, timeout_seconds: 60, temperature: 0, max_output_tokens: 4096 });

export default function LLMSettingsModal({ onClose, onChanged }: { onClose: () => void; onChanged: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [profiles, setProfiles] = useState<Profile[]>([]);
  const [presets, setPresets] = useState<Preset[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [draft, setDraft] = useState<Draft>(empty);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [protection, setProtection] = useState('');
  const selected = profiles.find(profile => profile.id === draft.id);
  const active = profiles.find(profile => profile.id === activeId);
  const preset = presets.find(item => item.id === draft.vendor);

  const reload = async () => {
    const result = await sspClient.call('listLLMProfiles', {});
    setProfiles(result.profiles); setActiveId(result.active_id); setProtection(result.credential_protection);
    return result.profiles as Profile[];
  };
  useEffect(() => {
    dialog.current?.showModal();
    setBusy(true);
    Promise.all([reload(), sspClient.call('listLLMPresets', {}).then(result => setPresets(result.presets))])
      .catch(reason => setError(reason.message)).finally(() => setBusy(false));
  }, []);

  const choose = (profile?: Profile) => {
    setDraft(profile ? { vendor: profile.vendor || 'custom', id: profile.id, name: profile.name, provider: profile.provider, model: profile.model,
      api_base_url: profile.api_base_url, api_key: '', clear_api_key: false, timeout_seconds: profile.timeout_seconds,
      temperature: profile.temperature, max_output_tokens: profile.max_output_tokens || 4096 } : empty());
    setMessage(''); setError('');
  };
  const chooseVendor = (vendor: string) => {
    const next = presets.find(item => item.id === vendor);
    if (!next) { setDraft({ ...draft, vendor: 'custom' }); return; }
    setDraft({ ...draft, vendor, provider: next.provider, api_base_url: next.api_base_url,
      name: !draft.name || draft.name === preset?.name ? next.name : draft.name,
      model: next.models[0] || '', api_key: '', clear_api_key: Boolean(selected?.has_api_key),
      temperature: 0, timeout_seconds: 120 });
    setError(''); setMessage("已填入厂商配置，请输入该厂商的 API Key；原有密钥不会自动带入。");
  };
  const run = async (action: () => Promise<void>) => {
    setBusy(true); setError(''); setMessage('');
    try { await action(); } catch (reason) { setMessage(''); setError(reason instanceof Error ? reason.message : t("操作失败")); }
    finally { setBusy(false); }
  };
  const save = (activate: boolean) => run(async () => {
    setMessage("正在验证接口连接，验证通过后才会保存…");
    const result = await sspClient.call('saveLLMProfile', { profile: draft, activate });
    const updated = await reload();
    choose(updated.find(profile => profile.id === result.profile.id));
    setMessage(activate ? t("验证通过，已保存并启用。下一次模型请求将使用此接口。") : t("连接验证通过，配置已保存。"));
    onChanged();
  });
  const activate = (id: string | null) => run(async () => {
    await sspClient.call('activateLLMProfile', { profile_id: id });
    await reload(); onChanged(); setMessage(id ? t("已切换当前接口，无需重启。") : t("已切换为服务器 .env 配置。"));
  });

  return <dialog ref={dialog} className="llm-settings" aria-labelledby="llm-settings-title"
    onCancel={event => { event.preventDefault(); onClose(); }}>
    <header><div><h2 id="llm-settings-title">{t("模型接口设置")}</h2><p>{t("保存多个接口，随时切换当前使用的模型。")}</p></div>
      <button type="button" aria-label={t("关闭接口设置")} onClick={onClose}>×</button></header>
    <div className="llm-settings-current">{t("当前使用：")}<strong>{active ? `${active.name} · ${active.model}` : t('服务器 .env 配置')}</strong></div>
    <div className="llm-settings-body">
      <aside aria-label={t("已保存接口")}>
        <button type="button" className="llm-new" disabled={busy} onClick={() => choose()}>{t("＋ 新增接口")}</button>
        {profiles.length === 0 && <p className="llm-hint">{t("尚未保存接口。先填写右侧配置。")}</p>}
        {profiles.map(profile => <button type="button" key={profile.id} disabled={busy}
          className={`llm-profile ${draft.id === profile.id ? 'selected' : ''}`} onClick={() => choose(profile)}>
          <span><strong>{profile.name}</strong>{activeId === profile.id && <em>{t("使用中")}</em>}</span>
          <small>{profile.model}</small><small>{profile.api_base_url}</small>
        </button>)}
        <button type="button" disabled={busy || !activeId} onClick={() => activate(null)}>{t("使用服务器 .env 配置")}</button>
      </aside>
      <form onSubmit={event => { event.preventDefault(); void save(false); }}>
        <h3>{draft.id ? t('编辑接口') : t('新增接口')}</h3>
        <fieldset disabled={busy}>
          <label className="llm-full">{t("厂商预设")}<select aria-label={t("厂商预设")} value={draft.vendor} onChange={event => chooseVendor(event.target.value)}>
            <option value="custom">{t("自定义 / 第三方中转")}</option>
            {presets.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}
          </select>
            {preset && <small>{preset.note} <a href={preset.source_url} target="_blank" rel="noreferrer">{t("官方文档")}</a></small>}
            {draft.vendor === 'zhipu' && <small>{t('Zhipu request queue')}</small>}
          </label>
          <label>{t("配置名称")}<input required maxLength={100} value={draft.name} placeholder={t("例如：日常抽取 / 备用接口")}
            onChange={event => setDraft({ ...draft, name: event.target.value })} /></label>
          <label>{t("接口类型")}<select aria-label={t("接口类型")} value={draft.provider} onChange={event => setDraft({ ...draft, vendor: 'custom', provider: event.target.value, api_key: '', clear_api_key: Boolean(selected?.has_api_key) })}>
            <option value="openai_compatible">{t("OpenAI 兼容接口")}</option><option value="ollama">Ollama</option>
            <option value="anthropic">{t("Claude / Anthropic 原生接口")}</option>
          </select></label>
          <label className="llm-full">{t('Base URL')}<input required type="url" value={draft.api_base_url}
            placeholder={draft.provider === 'ollama' ? 'http://localhost:11434' : 'https://你的服务地址/v1'}
            onChange={event => setDraft({ ...draft, api_base_url: event.target.value })} />
            <small>{t("填写服务根地址，不要附加 /chat/completions 或 /messages。保存时自动验证连接，切换不会重复调用模型。")}</small></label>
          {preset && preset.models.length > 0 && <label className="llm-full">{t("常用模型")}<select aria-label={t("常用模型")}
            value={preset.models.includes(draft.model) ? draft.model : ''} onChange={event => { if (event.target.value) setDraft({ ...draft, model: event.target.value }); }}>
            <option value="">{t("手动填写其他模型")}</option>{preset.models.map(model => <option key={model} value={model}>{model}</option>)}
          </select></label>}
          <label className="llm-full">{t("模型名称")}<input required maxLength={200} value={draft.model} placeholder={t("填写服务商提供的完整模型 ID")}
            onChange={event => setDraft({ ...draft, model: event.target.value })} /></label>
          <label className="llm-full">{t('API Key')}<input type="password" autoComplete="new-password" value={draft.api_key}
            placeholder={selected?.has_api_key ? t('已保存密钥；留空保持不变') : t('输入密钥；无需认证的本地服务可留空')}
            onChange={event => setDraft({ ...draft, api_key: event.target.value, clear_api_key: false })} />
            <small>{selected?.has_api_key ? t('已配置密钥。同一服务器下留空保留；更换服务器或协议需重新输入密钥。') : t('密钥仅发给本机后端保存，不写入浏览器存储。')}</small></label>
          {selected?.has_api_key && <label className="llm-full llm-checkbox"><input type="checkbox" checked={draft.clear_api_key}
            onChange={event => setDraft({ ...draft, clear_api_key: event.target.checked, api_key: '' })} />{t("清除此接口已保存的密钥")}</label>}
          <details className="llm-full llm-advanced"><summary>{t("高级设置（通常无需修改）")}</summary><div className="llm-advanced-fields">
          <label>{t("超时（秒）")}<input type="number" required min={1} max={600} value={draft.timeout_seconds}
            onChange={event => setDraft({ ...draft, timeout_seconds: Number(event.target.value) })} /></label>
          <label>{t("最大输出 tokens")}<input type="number" required min={1} max={131072} value={draft.max_output_tokens}
            onChange={event => setDraft({ ...draft, max_output_tokens: Number(event.target.value) })} /></label>
          <label>{t("Temperature")}<input type="number" required disabled={draft.provider === 'anthropic' || ['kimi', 'deepseek', 'zhipu'].includes(draft.vendor)} min={0} max={2} step={0.1} value={draft.temperature}
            onChange={event => setDraft({ ...draft, temperature: Number(event.target.value) })} /></label>
          {(draft.provider === 'anthropic' || ['kimi', 'deepseek', 'zhipu'].includes(draft.vendor)) && <small className="llm-full">{t("采样参数由模型默认处理，避免不兼容。模型列表为预设建议，具体可用性以你的厂商账户为准。")}</small>}
          </div></details>
        </fieldset>
        <div className="llm-settings-feedback" aria-live="polite">
          {busy && <p role="status">{t("正在处理，请稍候…")}</p>}
          {error && <p role="alert" className="llm-error">{localizeMessage(error)}</p>}
          {message && <p role="status">{localizeMessage(message)}</p>}
        </div>
        <div className="llm-actions">
          <button type="submit" disabled={busy}>{t("验证并保存配置")}</button>
          <button type="button" className="llm-primary" disabled={busy} onClick={event => {
            if (event.currentTarget.form?.reportValidity()) void save(true);
          }}>{t("验证并启用")}</button>
          {draft.id && <>
            <button type="button" disabled={busy || activeId === draft.id} onClick={() => activate(draft.id!)}>{t("切换到此接口")}</button>
            <button type="button" disabled={busy} onClick={() => run(async () => {
              const result = await sspClient.call('testLLMProfile', { profile_id: draft.id });
              const text = t('{message} ({seconds} seconds)', { message: t(result.message), seconds: result.seconds });
              if (result.healthy) setMessage(text); else setError(text);
              onChanged();
            })}>{t("测试已保存接口")}</button>
            <button type="button" className="llm-delete" disabled={busy} onClick={() => run(async () => {
              await sspClient.call('deleteLLMProfile', { profile_id: draft.id });
              await reload(); choose(); onChanged(); setMessage("接口已删除。删除当前接口后将使用服务器 .env 配置。");
            })}>{t("删除此接口")}</button>
          </>}
        </div>
        <p className="llm-hint">{t("保存和测试都会发送一条小请求并消耗少量 tokens；验证失败不会覆盖或启用新配置。当前请求不受切换影响，新请求立即使用新接口。")}</p>
        <p className="llm-hint">{t("本机密钥保护：")}{protection ? t(protection) : t('正在读取…')}{t("。配置按登录用户隔离，重启后保留。")}</p>
      </form>
    </div>
  </dialog>;
}
