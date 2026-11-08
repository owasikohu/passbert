browser.action.onClicked.addListener(async tab => {
  const id = crypto.randomUUID();
  let snapshot;
  try {
    const results = await browser.scripting.executeScript({target:{tabId:tab.id},files:['capture.js']});
    const capture = results[0]?.result;
    if (!capture) throw Error('抽出結果を取得できませんでした。');
    const bytes = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(capture.hostname));
    const site = [...new Uint8Array(bytes)].map(x=>x.toString(16).padStart(2,'0')).join('');
    snapshot = {id,snapshot_key:capture.snapshot_key,tabId:tab.id,site_id:'host-sha256:'+site,forms:capture.forms,visibility:capture.visibility,extraction_ms:capture.extraction_ms,captured_at:new Date().toISOString()};
  } catch (error) {
    snapshot = {id,error:'このページを読み取れません。通常のHTTPSページで実行してください。ブラウザ内蔵ページやアクセス制限のあるページは対象外です。'};
  }
  const previous=await browser.storage.session.get(null);
  const stale=Object.keys(previous).slice(0,Math.max(0,Object.keys(previous).length-19));
  if(stale.length)await browser.storage.session.remove(stale);
  await browser.storage.session.set({[id]:snapshot});
  await browser.tabs.create({url:browser.runtime.getURL('review.html')+'?id='+encodeURIComponent(id)});
});
