(function(){
  const modal = document.getElementById("authModal");
  if (!modal) return;

  // mở modal khi click vào bất kỳ phần tử có data-open-auth
  document.querySelectorAll("[data-open-auth]").forEach(el=>{
    el.addEventListener("click", ()=> modal.classList.remove("hidden"));
  });
  modal.querySelectorAll("[data-close]").forEach(el=>{
    el.addEventListener("click", ()=> modal.classList.add("hidden"));
  });

  const tabLogin = document.getElementById("tabLogin");
  const tabRegister = document.getElementById("tabRegister");
  const formLogin = document.getElementById("formLogin");
  const formRegister = document.getElementById("formRegister");
  const formGuest = document.getElementById("formGuest");
  const toggleGuest = document.getElementById("toggleGuest");

  function showLogin(){
    formLogin.classList.remove("hidden");
    formRegister.classList.add("hidden");
    tabLogin.classList.add("bg-white","text-black","font-semibold");
    tabRegister.classList.remove("bg-white","text-black","font-semibold");
    tabRegister.classList.add("bg-blue-600");
  }
  function showRegister(){
    formRegister.classList.remove("hidden");
    formLogin.classList.add("hidden");
    tabRegister.classList.add("bg-white","text-black","font-semibold");
    tabLogin.classList.remove("bg-white","text-black","font-semibold");
    tabLogin.classList.add("bg-blue-600");
  }
  tabLogin.addEventListener("click", showLogin);
  tabRegister.addEventListener("click", showRegister);
  toggleGuest && toggleGuest.addEventListener("click", ()=> formGuest.classList.toggle("hidden"));

  async function postForm(form, errorBoxId){
    const fd = new FormData(form);
    const res = await fetch(form.action, {
      method: "POST",
      headers: {"X-Requested-With": "XMLHttpRequest"},
      body: fd
    });
    const data = await res.json().catch(()=> ({}));
    const errEl = document.getElementById(errorBoxId);
    if (data.ok){
      errEl && (errEl.textContent = "");
      return data;
    }
    let msg = "Có lỗi xảy ra.";
    if (data.errors){
      msg = Object.entries(data.errors).map(([k,v])=>`${k}: ${Array.isArray(v)?v.join(", "):v}`).join(" | ");
    }
    errEl && (errEl.textContent = msg);
    throw new Error(msg);
  }

  formLogin.addEventListener("submit", async (e)=>{
    e.preventDefault();
    try { await postForm(formLogin, "loginErrors"); window.location.reload(); } catch (e) {}
  });
  formRegister.addEventListener("submit", async (e)=>{
    e.preventDefault();
    try { await postForm(formRegister, "registerErrors"); window.location.reload(); } catch (e) {}
  });
  formGuest.addEventListener("submit", async (e)=>{
    e.preventDefault();
    try {
      const data = await postForm(formGuest, "guestErrors");
      const list = document.getElementById("commentList");
      if (list){
        const item = document.createElement("div");
        item.className = "border-b border-gray-700 pb-3";
        item.innerHTML = `<div class="text-sm text-gray-400">${data.comment.author} • ${data.comment.created_at}</div>
                          <div class="mt-1">${data.comment.content}</div>`;
        list.prepend(item);
      }
      modal.classList.add("hidden");
      formGuest.reset();
    } catch (e) {}
  });

  // default tab
  showLogin();
})();
