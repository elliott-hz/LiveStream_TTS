import { useState, useEffect } from "react";

interface Product {
  id: string; name: string; sku: string; category: string;
  platform_kbs: { platform: string; platform_name: string; price: string }[];
}

export default function ProductPage() {
  const [products, setProducts] = useState<Product[]>([]);
  const [importOpen, setImportOpen] = useState(false);
  const [importUrl, setImportUrl] = useState("");
  const [importPlatform, setImportPlatform] = useState("taobao");

  useEffect(() => {
    fetch("/api/products").then(r => r.json()).then(setProducts);
  }, []);

  const handleCreate = async () => {
    const name = prompt("商品名称:");
    if (!name) return;
    const sku = prompt("SKU:") || "";
    await fetch("/api/products", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, sku, category: "" }),
    });
    location.reload();
  };

  const handleImport = async () => {
    await fetch("/api/products/import", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ platform: importPlatform, url: importUrl }),
    });
    setImportOpen(false);
    location.reload();
  };

  const handleDelete = async (id: string) => {
    if (!confirm("确认删除?")) return;
    await fetch(`/api/products/${id}`, { method: "DELETE" });
    setProducts(prev => prev.filter(p => p.id !== id));
  };

  return (
    <div>
      <div style={{ marginBottom: 16, display: "flex", gap: 8 }}>
        <button className="btn-primary" onClick={handleCreate}>+ 手动添加</button>
        <button className="btn-outline" onClick={() => setImportOpen(true)}>📥 AI 导入</button>
      </div>

      <div className="card">
        <div className="card-header"><h3>🛒 商品列表</h3></div>
        <div className="card-body">
          <table>
            <thead><tr><th>名称</th><th>SKU</th><th>分类</th><th>平台知识库</th><th>操作</th></tr></thead>
            <tbody>
              {products.map(p => (
                <tr key={p.id}>
                  <td><strong>{p.name}</strong></td>
                  <td>{p.sku}</td>
                  <td><span className="tag tag-neutral">{p.category || "—"}</span></td>
                  <td>
                    {p.platform_kbs.map(kb => (
                      <span key={kb.platform} className="tag tag-success" style={{ marginRight: 4 }}>
                        {kb.platform} {kb.price}
                      </span>
                    ))}
                    {p.platform_kbs.length === 0 && <span className="text-muted">未导入</span>}
                  </td>
                  <td>
                    <button className="btn-outline btn-sm" onClick={() => { setImportPlatform("taobao"); setImportOpen(true); }}>导入</button>
                    {" "}
                    <button className="btn-outline btn-sm" style={{ color: "var(--danger)" }} onClick={() => handleDelete(p.id)}>删除</button>
                  </td>
                </tr>
              ))}
              {products.length === 0 && (
                <tr><td colSpan={5} style={{ textAlign: "center", color: "var(--text-muted)", padding: 40 }}>暂无商品，点击上方添加</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Import Modal */}
      {importOpen && (
        <div className="modal-overlay" onClick={() => setImportOpen(false)}>
          <div className="modal" onClick={e => e.stopPropagation()} style={{ maxWidth: 500 }}>
            <div className="modal-header">
              <h3>📥 AI 导入商品</h3>
              <button className="btn-outline btn-sm" onClick={() => setImportOpen(false)}>✕</button>
            </div>
            <div className="modal-body">
              <div className="form-group">
                <label>平台</label>
                <select value={importPlatform} onChange={e => setImportPlatform(e.target.value)}>
                  <option value="taobao">淘宝</option>
                  <option value="douyin">抖音</option>
                  <option value="kuaishou">快手</option>
                  <option value="jd">京东</option>
                  <option value="pdd">拼多多</option>
                </select>
              </div>
              <div className="form-group">
                <label>商品链接</label>
                <input placeholder="粘贴平台商品详情页链接" value={importUrl} onChange={e => setImportUrl(e.target.value)} />
              </div>
            </div>
            <div className="modal-footer">
              <button className="btn-outline" onClick={() => setImportOpen(false)}>取消</button>
              <button className="btn-primary" onClick={handleImport}>开始导入</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
