() => {
  // Stable per-document IDs and direct Element references, including open shadow roots.
  const state = window.__applylocal_state ||= {seq: 0, ids: new WeakMap(), nodes: new Map()};
  const id = el => {
    if (!state.ids.has(el)) state.ids.set(el, 'c' + (++state.seq));
    const value = state.ids.get(el); state.nodes.set(value, el); return value;
  };
  const roots = [document];
  for (let i = 0; i < roots.length; i++)
    for (const el of roots[i].querySelectorAll('*')) if (el.shadowRoot) roots.push(el.shadowRoot);
  const all = sel => roots.flatMap(r => Array.from(r.querySelectorAll(sel)));
  const clean = text => (text || '').replace(/\s+/g, ' ').trim();
  const visible = el => {
    const s = getComputedStyle(el);
    return s.visibility !== 'hidden' && s.display !== 'none'
      && Array.from(el.getClientRects()).some(r => r.width > 0 && r.height > 0)
      && !el.closest('[inert],[aria-hidden="true"]');
  };
  const text = el => clean(el?.innerText || el?.textContent);
  const byId = (el, value) => el.getRootNode().getElementById?.(value) || document.getElementById(value);
  const labelled = el => clean((el.getAttribute('aria-labelledby') || '').split(/\s+/)
    .map(i => text(byId(el, i))).join(' '));
  const label = el => clean(labelled(el) || el.getAttribute('aria-label')
    || Array.from(el.labels || []).map(text).join(' ') || text(el.closest('label'))
    || el.getAttribute('placeholder') || (el.matches('[role]') ? text(el) : '') || el.title);
  const group = el => el.closest('fieldset,[role="radiogroup"],[data-question],.question,[role="group"]');
  const prompt = (el, container) => clean(
    (container && (labelled(container) || container.getAttribute('aria-label')
      || text(container.querySelector('legend,[data-prompt],.question-text,.statement,.question-title,.input__label,[role="heading"],h1,h2,h3,h4'))))
    || label(el) || 'Unlabeled question');
  const globalProse = clean(all('p,[data-context],.scenario-text,[data-scenario],.instructions')
    .filter(el => visible(el) && !el.closest('label,[role="option"],[role="timer"],.timer,.countdown,[role="alert"],.error,.validation-error,[aria-live]')
      && !group(el))
    .map(text).join(' '));
  const context = el => {
    const container = group(el);
    const area = container?.closest('[data-scenario],.scenario,.question-container') || container;
    if (!area) return globalProse;
    return clean(Array.from(area.querySelectorAll('p,[data-context],.scenario-text'))
      .filter(el => visible(el) && !el.closest('[role="alert"],.error,.validation-error,[aria-live]')).map(text).join(' ')) || globalProse;
  };
  const disabled = el => el.disabled || el.getAttribute('aria-disabled') === 'true';
  const checked = el => el.checked === true || el.getAttribute('aria-checked') === 'true'
    || el.getAttribute('aria-selected') === 'true';
  const invalid = el => !!(el.willValidate && !el.validity.valid)
    || (!el.willValidate && el.getAttribute('aria-invalid') === 'true');
  const scaleLabels = (peers, container) => {
    if (!container || ![3,5,7].includes(peers.length)) return null;
    const anchors = Array.from(container.querySelectorAll('span,div,p,label'))
      .filter(el => visible(el) && !el.querySelector('input,button,[role="radio"]')
        && /^(?:agree|disagree)$/i.test(text(el)));
    const agree = anchors.find(el => /^agree$/i.test(text(el)));
    const disagree = anchors.find(el => /^disagree$/i.test(text(el)));
    if (!agree || !disagree) return null;
    const center = el => {const r=el.getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2};};
    const points = peers.map(p => center(visible(p) ? p : Array.from(p.labels||[]).find(visible) || p));
    const axis = Math.abs(center(agree).x-center(disagree).x) > Math.abs(center(agree).y-center(disagree).y) ? 'x' : 'y';
    const order = peers.map((p,i)=>({p,value:points[i][axis]})).sort((a,b)=>a.value-b.value);
    if (new Set(order.map(v=>v.value)).size !== peers.length) return null;
    const lower = order[0].value, upper = order[order.length-1].value;
    const a = center(agree)[axis], d = center(disagree)[axis];
    if (!(Math.min(a,d)<lower && Math.max(a,d)>upper)) return null;
    const captions = peers.length===7 ? ['Strongly agree','Moderately agree','Agree','Neither agree nor disagree','Disagree','Moderately disagree','Strongly disagree']
      : peers.length===5 ? ['Strongly agree','Agree','Neither agree nor disagree','Disagree','Strongly disagree']
      : ['Agree','Neither agree nor disagree','Disagree'];
    if (a>d) captions.reverse();
    return new Map(order.map((item,i)=>[item.p,captions[i]]));
  };
  const questions = [], used = new Set();
  const controls = all('input:not([type="hidden"]):not([type="submit"]):not([type="button"]):not([type="reset"]),textarea,select,[role="radio"],[role="checkbox"],[role="combobox"]')
    .filter(el => visible(el) || (el.matches('input[type="radio"],input[type="checkbox"]')
      && Array.from(el.labels||[]).some(visible)));
  for (const el of controls) {
    if (used.has(el) || disabled(el)) continue;
    const role = el.getAttribute('role');
    const type = role === 'radio' || role === 'checkbox' ? role : el.type;
    const container = group(el);
    if (type === 'radio' || type === 'checkbox') {
      const peers = controls.filter(other => {
        if ((other.getAttribute('role') || other.type) !== type) return false;
        if (type === 'radio' && el.name) return other.name === el.name && other.form === el.form
          && other.getRootNode() === el.getRootNode();
        return container ? group(other) === container : other === el;
      });
      peers.forEach(p => used.add(p));
      const scale = type === 'radio' ? scaleLabels(peers, container) : null;
      questions.push({id: id(el), prompt: prompt(el, container), context: context(el), kind: type,
        options: peers.map(p => ({id: id(p), label: scale?.get(p) || label(p) || p.value || 'Unlabeled option',
          selected: checked(p), disabled: disabled(p)})), value: '',
        required: peers.some(p => p.required || p.getAttribute('aria-required') === 'true'),
        invalid: peers.some(p => p.willValidate && !p.validity.valid)
          || (!peers.some(checked) && peers.some(p => p.getAttribute('aria-invalid') === 'true')),
        sensitive: false});
    } else if (el.tagName === 'SELECT') {
      used.add(el);
      questions.push({id: id(el), prompt: prompt(el, null), context: context(el), kind: el.multiple ? 'checkbox' : 'select',
        options: Array.from(el.options).filter(o => o.value !== '').map(o => ({id: id(o),
          label: text(o), selected: o.selected, disabled: disabled(o) || disabled(o.parentElement)})),
        value: '', required: el.required, invalid: invalid(el), sensitive: false});
    } else if (role === 'combobox') {
      used.add(el);
      const list = byId(el, el.getAttribute('aria-controls') || el.getAttribute('aria-owns') || '');
      const options = list ? Array.from(list.querySelectorAll('[role="option"]')) : [];
      questions.push({id: id(el), prompt: label(el), context: context(el), kind: 'combobox', value: '',
        options: options.map(o => ({id: id(o), label: text(o), selected: checked(o), disabled: disabled(o)})),
        required: el.getAttribute('aria-required') === 'true',
        invalid: invalid(el) && !options.some(checked), sensitive: false});
    } else {
      used.add(el);
      questions.push({id: id(el), prompt: prompt(el, null), context: context(el), kind: 'text', options: [],
        value: el.value || '', required: !!el.required,
        invalid: invalid(el),
        sensitive: ['password','file'].includes(type) || el.autocomplete === 'one-time-code'});
    }
  }
  const buttons = all('button,input[type="submit"],input[type="button"],[role="button"],a')
    .filter(visible).map(el => ({id: id(el), label: label(el) || text(el) || el.value || '',
      disabled: !!disabled(el), submit: el.type === 'submit'}));
  const errors = all('[role="alert"],.error,.validation-error')
    .filter(visible).map(text).filter(Boolean);
  controls.filter(el => invalid(el) && (el.value || el.matches(':user-invalid')))
    .forEach(el => errors.push(el.validationMessage || 'Invalid field'));
  const visibleText = clean([document.body?.innerText, ...roots.slice(1).flatMap(root =>
    Array.from(root.children).filter(visible).map(text))].join(' ')).slice(0, 120000);
  const frames = all('iframe').filter(visible);
  const pageMarker = clean(all('h1,h2,[aria-current="step"],.page-number,.step-number,[data-page-number]')
    .filter(el => visible(el) && !group(el)).map(text).join(' '));
  return {questions, buttons, errors, text: visibleText,
    page_marker: pageMarker,
    busy: document.readyState === 'loading' || all('[aria-busy="true"]').some(visible)
      || buttons.some(b => /^(?:loading|submitting|please wait|processing)[\s.\u2026!]*$/i.test(b.label)),
    completion_candidates: all('h1,h2,h3,p,[role="status"]').filter(visible).map(text),
    authentication: controls.some(el => el.type === 'password') || frames.some(el => /recaptcha|hcaptcha|challenges.cloudflare/.test(el.src)),
    visual: all('canvas,img[role="application"],[role="application"]').some(visible)};
}
