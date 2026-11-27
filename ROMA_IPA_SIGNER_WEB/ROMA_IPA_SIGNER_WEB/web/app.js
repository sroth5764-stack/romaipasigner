const $ = id => document.getElementById(id);
const files = {ipa:null,p12:null,profile:null};
for (const key of Object.keys(files)) {
  $(key).addEventListener("change", () => {
    files[key] = $(key).files[0] || null;
    const labels = {ipa:"ipaName",p12:"p12Name",profile:"profileName"};
    $(labels[key]).textContent = files[key] ? `${files[key].name} · ${formatSize(files[key].size)}` : "No file selected";
  });
}
function formatSize(n){return n < 1048576 ? `${(n/1024).toFixed(0)} KB` : `${(n/1048576).toFixed(1)} MB`;}
function log(message){$("log").textContent = message;}
function progress(value,title){$("progressBar").style.width = `${value}%`;$("statusPct").textContent=`${value}%`;$("statusTitle").textContent=title;}
async function checkHealth(){
  try { const r=await fetch("/api/health"); if(!r.ok) throw Error(); $("serverStatus").textContent="MAC ONLINE"; $("serverStatus").style.color="#8af0b0"; }
  catch { $("serverStatus").textContent="SERVICE OFFLINE"; }
}
$("signBtn").addEventListener("click", async () => {
  if(!files.ipa || !files.p12 || !files.profile || !$("p12Password").value || !$("token").value){
    log("Select all three files and enter the certificate password and access token."); return;
  }
  $("signBtn").disabled=true; $("downloadLink").classList.add("hidden"); progress(10,"UPLOADING"); log("Uploading files securely to the configured Mac service…");
  const data=new FormData(); data.append("ipa",files.ipa); data.append("p12",files.p12); data.append("profile",files.profile); data.append("p12_password",$("p12Password").value);
  try{
    const response=await fetch("/api/sign",{method:"POST",headers:{"X-ROMA-TOKEN":$("token").value},body:data});
    const result=await response.json();
    if(!response.ok) throw new Error(result.error || "Signing failed");
    progress(100,"COMPLETE"); log(result.message || "Signing completed and verified.");
    $("downloadLink").href=result.download_url; $("downloadLink").classList.remove("hidden");
  }catch(e){progress(0,"FAILED");log(`ERROR: ${e.message}`);}
  finally{$("signBtn").disabled=false;}
});
checkHealth();
