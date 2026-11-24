import { useEffect, useMemo, useState } from 'react'
import { Alert, Autocomplete, Avatar, Box, Button, Card, CardContent, Chip, CircularProgress, Container, Dialog, DialogActions, DialogContent, DialogTitle, Divider, IconButton, InputAdornment, Stack, TextField, Typography } from '@mui/material'
import AddRounded from '@mui/icons-material/AddRounded'
import CampaignRounded from '@mui/icons-material/CampaignRounded'
import DeleteOutlineRounded from '@mui/icons-material/DeleteOutlineRounded'
import FileDownloadOutlined from '@mui/icons-material/FileDownloadOutlined'
import EditRounded from '@mui/icons-material/EditRounded'
import SearchRounded from '@mui/icons-material/SearchRounded'
import PublicRounded from '@mui/icons-material/PublicRounded'

type Offer = { id: number; name: string; position: number; weight: number; keitaro_offer_id: number }
type Campaign = { id: number; name: string; country: string; offer_id: number; keitaro_id: number | null; status: string; offers: Offer[] }
type RemoteOffer = { id: number; name: string }
type Country = { code: string; name: string; flag: string }
const countryCodes = 'AD AE AF AG AI AL AM AO AQ AR AS AT AU AW AX AZ BA BB BD BE BF BG BH BI BJ BL BM BN BO BQ BR BS BT BV BW BY BZ CA CC CD CF CG CH CI CK CL CM CN CO CR CU CV CW CX CY CZ DE DJ DK DM DO DZ EC EE EG EH ER ES ET FI FJ FK FM FO FR GA GB GD GE GF GG GH GI GL GM GN GP GQ GR GS GT GU GW GY HK HM HN HR HT HU ID IE IL IM IN IO IQ IR IS IT JE JM JO JP KE KG KH KI KM KN KP KR KW KY KZ LA LB LC LI LK LR LS LT LU LV LY MA MC MD ME MF MG MH MK ML MM MN MO MP MQ MR MS MT MU MV MW MX MY MZ NA NC NE NF NG NI NL NO NP NR NU NZ OM PA PE PF PG PH PK PL PM PN PR PS PT PW PY QA RE RO RS RU RW SA SB SC SD SE SG SH SI SJ SK SL SM SN SO SR SS ST SV SX SY SZ TC TD TF TG TH TJ TK TL TM TN TO TR TT TV TW TZ UA UG UM US UY UZ VA VC VE VG VI VN VU WF WS YE YT ZA ZM ZW'.split(' ')
const countryNames = new Intl.DisplayNames(['ru'], { type: 'region' })
const countries: Country[] = countryCodes.map(code => ({
  code,
  name: countryNames.of(code) ?? code,
  flag: String.fromCodePoint(...[...code].map(letter => letter.charCodeAt(0) + 127397)),
})).sort((a, b) => a.name.localeCompare(b.name, 'ru'))
const countryByCode = (code: string) => countries.find(country => country.code === code.toUpperCase())
const api = async <T,>(path: string, init?: RequestInit): Promise<T> => {
  const response = await fetch(`/api${path}`, { ...init, headers: { 'Content-Type': 'application/json', ...init?.headers } })
  if (!response.ok) {
    const raw = await response.text()
    let message = raw
    try { const body = JSON.parse(raw); message = body.detail || body.message || raw } catch { /* Keep the raw server response for diagnostics. */ }
    throw new Error(message || `Request failed (${response.status})`)
  }
  return response.json()
}
const initials = (name: string) => name.split(/\s+/).slice(0, 2).map(x => x[0]).join('').toUpperCase()
const formatShare = (share: number) => Number(share.toFixed(2)).toString()

export default function App() {
  const [campaigns, setCampaigns] = useState<Campaign[]>([])
  const [selected, setSelected] = useState<number | null>(null)
  const [query, setQuery] = useState('')
  const [offers, setOffers] = useState<RemoteOffer[]>([])
  const [name, setName] = useState('')
  const [country, setCountry] = useState<Country>(countryByCode('AU')!)
  const [createOffer, setCreateOffer] = useState<RemoteOffer | null>(null)
  const [addOffer, setAddOffer] = useState<RemoteOffer | null>(null)
  const [createOpen, setCreateOpen] = useState(false)
  const [importOpen, setImportOpen] = useState(false)
  const [importId, setImportId] = useState('')
  const [editOpen, setEditOpen] = useState(false)
  const [editName, setEditName] = useState('')
  const [editCountry, setEditCountry] = useState<Country>(countryByCode('AU')!)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const current = campaigns.find(c => c.id === selected) ?? null

  const loadCampaigns = async () => {
    try { const data = await api<Campaign[]>('/campaigns'); setCampaigns(data); setSelected(s => s ?? data[0]?.id ?? null) } catch (e) { setError((e as Error).message) }
  }
  useEffect(() => { void loadCampaigns() }, [])
  useEffect(() => {
    const timer = setTimeout(async () => {
      try { setOffers(await api<RemoteOffer[]>(`/offers?q=${encodeURIComponent(query)}`)) } catch (e) { setError((e as Error).message) }
    }, 250)
    return () => clearTimeout(timer)
  }, [query])
  const weighted = useMemo(() => Number((current?.offers.reduce((sum, offer) => sum + offer.weight, 0) ?? 0).toFixed(2)), [current])

  const create = async () => {
    if (!name.trim() || !createOffer) return
    setLoading(true); setError('')
    try {
      const campaign = await api<Campaign>('/campaigns', { method: 'POST', body: JSON.stringify({ name: name.trim(), country: country.code, offer_id: createOffer.id }) })
      await loadCampaigns(); setCampaigns(old => [campaign, ...old.filter(c => c.id !== campaign.id)]); setSelected(campaign.id); setCreateOpen(false); setName(''); setCreateOffer(null)
    } catch (e) { setError((e as Error).message) } finally { setLoading(false) }
  }
  const importExisting = async () => {
    const keitaroId = Number(importId)
    if (!Number.isInteger(keitaroId) || keitaroId <= 0) return
    setLoading(true); setError('')
    try {
      const campaign = await api<Campaign>('/campaigns/import', { method: 'POST', body: JSON.stringify({ keitaro_id: keitaroId }) })
      setCampaigns(rows => [campaign, ...rows.filter(c => c.id !== campaign.id)]); setSelected(campaign.id); setImportOpen(false); setImportId('')
    } catch (e) { setError((e as Error).message) } finally { setLoading(false) }
  }
  const add = async () => {
    if (!current || !addOffer) return
    setLoading(true); setError('')
    try { const updated = await api<Campaign>(`/campaigns/${current.id}/offers`, { method: 'POST', body: JSON.stringify({ offer_id: addOffer.id }) }); setCampaigns(rows => rows.map(c => c.id === updated.id ? updated : c)); setAddOffer(null) }
    catch (e) { setError((e as Error).message) } finally { setLoading(false) }
  }
  const remove = async (row: Offer) => {
    if (!current) return
    setLoading(true); setError('')
    try { const updated = await api<Campaign>(`/campaigns/${current.id}/offers/${row.id}`, { method: 'DELETE' }); setCampaigns(rows => rows.map(c => c.id === updated.id ? updated : c)) }
    catch (e) { setError((e as Error).message) } finally { setLoading(false) }
  }
  const openEditor = () => {
    if (!current) return
    setEditName(current.name)
    setEditCountry(countryByCode(current.country) ?? countryByCode('AU')!)
    setEditOpen(true)
  }
  const saveCampaign = async () => {
    if (!current || !editName.trim()) return
    setLoading(true); setError('')
    try {
      const updated = await api<Campaign>(`/campaigns/${current.id}`, { method: 'PUT', body: JSON.stringify({ name: editName.trim(), country: editCountry.code }) })
      setCampaigns(rows => rows.map(c => c.id === updated.id ? updated : c)); setEditOpen(false)
    } catch (e) { setError((e as Error).message) } finally { setLoading(false) }
  }

  return <Box sx={{ minHeight: '100vh', bgcolor: 'background.default', pb: 7 }}>
    <Box sx={{ bgcolor: 'white', borderBottom: '1px solid #e9ecf2' }}><Container maxWidth="lg"><Stack direction="row" alignItems="center" justifyContent="space-between" sx={{ height: 72 }}><Stack direction="row" alignItems="center" spacing={1.5}><Avatar sx={{ bgcolor: 'primary.main', width: 36, height: 36, borderRadius: 2 }}><CampaignRounded fontSize="small"/></Avatar><Typography fontWeight={800} letterSpacing="-.4px">adrobot<span style={{ color: '#3b6df6' }}>.</span></Typography><Chip size="small" label="KEITARO MANAGER" sx={{ fontSize: 10, fontWeight: 750, letterSpacing: .6, bgcolor: '#f1f4ff', color: '#5771cf' }}/></Stack><Stack direction="row" spacing={1} alignItems="center"><Box sx={{ width: 8, height: 8, borderRadius: '50%', bgcolor: '#23b886' }}/><Typography variant="caption" color="text.secondary">Keitaro API</Typography></Stack></Stack></Container></Box>
    <Container maxWidth="lg" sx={{ pt: 5 }}>
      <Stack direction={{ xs: 'column', sm: 'row' }} alignItems={{ sm: 'flex-end' }} justifyContent="space-between" spacing={2} sx={{ mb: 3.5 }}><Box><Typography variant="overline" color="primary.main" fontWeight={800} letterSpacing={1.4}>WORKSPACE / TRACKING</Typography><Typography variant="h4" fontWeight={800} letterSpacing="-1.2px" sx={{ mt: .3 }}>Кампании</Typography><Typography color="text.secondary" sx={{ mt: .6 }}>Создавайте маршруты трафика и управляйте офферами</Typography></Box><Stack direction="row" spacing={1}><Button variant="outlined" startIcon={<FileDownloadOutlined/>} onClick={() => setImportOpen(true)}>Открыть из Keitaro</Button><Button variant="contained" startIcon={<AddRounded/>} onClick={() => setCreateOpen(true)}>Новая кампания</Button></Stack></Stack>
      {error && <Alert severity="error" onClose={() => setError('')} sx={{ mb: 2 }}>{error}</Alert>}
      <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', md: '310px minmax(0, 1fr)' }, gap: 2.5, alignItems: 'start' }}>
        <Card><CardContent sx={{ p: 2.2, '&:last-child': { pb: 2.2 } }}><Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 1.5 }}><Typography fontWeight={750}>Все кампании</Typography><Chip size="small" label={campaigns.length} sx={{ height: 23, bgcolor: '#f1f3f8' }}/></Stack><TextField size="small" placeholder="Найти кампанию" fullWidth sx={{ mb: 1.5 }} InputProps={{ startAdornment: <InputAdornment position="start"><SearchRounded fontSize="small" color="action"/></InputAdornment> }}/><Stack spacing={.6}>{campaigns.map(c => <Box key={c.id} onClick={() => setSelected(c.id)} sx={{ display: 'flex', alignItems: 'center', gap: 1.3, p: 1.2, borderRadius: 2, cursor: 'pointer', bgcolor: selected === c.id ? '#f0f4ff' : 'transparent', '&:hover': { bgcolor: '#f6f7fa' } }}><Avatar sx={{ width: 34, height: 34, fontSize: 12, fontWeight: 750, bgcolor: selected === c.id ? '#dce5ff' : '#eff1f6', color: selected === c.id ? 'primary.main' : '#737c90' }}>{initials(c.name)}</Avatar><Box sx={{ minWidth: 0, flex: 1 }}><Typography noWrap fontSize={13} fontWeight={700}>{c.name}</Typography><Typography variant="caption" color="text.secondary">{c.country} · {c.offers.length} оффер{c.offers.length === 1 ? '' : 'а'}</Typography></Box><Box sx={{ width: 7, height: 7, borderRadius: '50%', bgcolor: '#23b886' }}/></Box>)}{campaigns.length === 0 && <Typography color="text.secondary" variant="body2" sx={{ py: 3, textAlign: 'center' }}>Кампаний пока нет</Typography>}</Stack></CardContent></Card>
        {current ? <Stack spacing={2.5}><Card><CardContent sx={{ p: { xs: 2.2, sm: 3 } }}><Stack direction={{ xs: 'column', sm: 'row' }} justifyContent="space-between" alignItems={{ sm: 'flex-start' }} spacing={2}><Stack direction="row" spacing={1.7} alignItems="center"><Avatar sx={{ width: 48, height: 48, borderRadius: 2.5, bgcolor: '#eef2ff', color: 'primary.main' }}><CampaignRounded/></Avatar><Box><Typography variant="h6" fontWeight={800}>{current.name}</Typography><Stack direction="row" spacing={1} alignItems="center" sx={{ mt: .3 }}><Chip size="small" icon={<PublicRounded sx={{ fontSize: '15px !important' }}/>} label={current.country} sx={{ height: 22, fontWeight: 700, bgcolor: '#f1f4ff', color: '#536bc0' }}/><Typography variant="caption" color="text.secondary">ID {current.keitaro_id ?? '—'}</Typography></Stack></Box></Stack><Stack direction="row" spacing={1} alignItems="center"><Chip size="small" label={current.status === 'disabled' ? 'Выключена' : 'Активна'} sx={{ fontWeight: 700, bgcolor: current.status === 'disabled' ? '#fff4e5' : '#e9f8f2', color: current.status === 'disabled' ? '#986300' : '#14845f' }}/><IconButton aria-label="Редактировать кампанию" onClick={openEditor} size="small"><EditRounded fontSize="small"/></IconButton></Stack></Stack><Divider sx={{ my: 2.5 }}/><Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.2}><Card variant="outlined" sx={{ flex: 1, boxShadow: 'none' }}><CardContent sx={{ p: 1.8, '&:last-child': { pb: 1.8 } }}><Typography variant="caption" color="text.secondary">ОФФЕРОВ В РОТАЦИИ</Typography><Typography variant="h5" fontWeight={800}>{current.offers.length}</Typography></CardContent></Card><Card variant="outlined" sx={{ flex: 1, boxShadow: 'none' }}><CardContent sx={{ p: 1.8, '&:last-child': { pb: 1.8 } }}><Typography variant="caption" color="text.secondary">СУММА ДОЛЕЙ</Typography><Typography variant="h5" fontWeight={800} color={weighted === 100 ? 'success.main' : 'error.main'}>{weighted}%</Typography></CardContent></Card><Card variant="outlined" sx={{ flex: 1, boxShadow: 'none' }}><CardContent sx={{ p: 1.8, '&:last-child': { pb: 1.8 } }}><Typography variant="caption" color="text.secondary">ГЕО ФИЛЬТР</Typography><Typography variant="h5" fontWeight={800}>{current.country}</Typography></CardContent></Card></Stack></CardContent></Card>
          <Card><CardContent sx={{ p: { xs: 2.2, sm: 3 } }}><Stack direction="row" justifyContent="space-between" alignItems="flex-start" spacing={2} sx={{ mb: 2 }}><Box><Typography variant="h6" fontWeight={800}>Офферы</Typography><Typography variant="body2" color="text.secondary" sx={{ mt: .35 }}>Распределение трафика между лендингами</Typography></Box><Chip size="small" label={`${current.offers.length} шт.`} sx={{ fontWeight: 700 }}/></Stack><Box sx={{ display: 'grid', gridTemplateColumns: 'minmax(0,1fr) 90px 42px', gap: 1, px: 1.5, pb: 1, color: 'text.secondary' }}><Typography variant="caption" fontWeight={700}>ОФФЕР</Typography><Typography variant="caption" fontWeight={700} textAlign="right">ДОЛЯ</Typography><span/></Box><Stack spacing={.8}>{current.offers.map((o, index) => <Box key={o.id} sx={{ display: 'grid', gridTemplateColumns: 'minmax(0,1fr) 90px 42px', alignItems: 'center', gap: 1, p: 1.25, border: '1px solid #eaedf3', borderRadius: 2 }}><Stack direction="row" alignItems="center" spacing={1.2} sx={{ minWidth: 0 }}><Avatar variant="rounded" sx={{ width: 34, height: 34, fontSize: 12, bgcolor: index % 2 ? '#f4edff' : '#eaf6ff', color: index % 2 ? '#8055c7' : '#4088ba' }}>{index + 1}</Avatar><Box sx={{ minWidth: 0 }}><Typography fontSize={13} fontWeight={700} noWrap>{o.name}</Typography><Typography variant="caption" color="text.secondary">Keitaro offer #{o.keitaro_offer_id}</Typography></Box></Stack><Typography fontWeight={750} textAlign="right">{formatShare(o.weight)}%</Typography><IconButton aria-label="Удалить оффер" size="small" onClick={() => void remove(o)} disabled={loading}><DeleteOutlineRounded fontSize="small"/></IconButton></Box>)}</Stack>{current.offers.length === 0 && <Typography variant="body2" color="text.secondary" sx={{ py: 1.5, textAlign: 'center' }}>В потоке пока нет офферов. Добавьте оффер ниже.</Typography>}<Divider sx={{ my: 2 }}/><Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', sm: 'minmax(0,1fr) auto' }, gap: 1.2 }}><Autocomplete options={offers} value={addOffer} onChange={(_, value) => setAddOffer(value)} inputValue={query} onInputChange={(_, value) => setQuery(value)} getOptionLabel={o => `${o.name} (#${o.id})`} isOptionEqualToValue={(a, b) => a.id === b.id} renderInput={params => <TextField {...params} size="small" placeholder="Найти оффер по названию или ID"/>}/><Button variant="outlined" startIcon={<AddRounded/>} onClick={() => void add()} disabled={!addOffer || loading}>Добавить оффер</Button></Box></CardContent></Card>
        </Stack> : <Card sx={{ minHeight: 340, display: 'grid', placeItems: 'center' }}><Stack alignItems="center" spacing={1.2} sx={{ p: 4 }}><Avatar sx={{ bgcolor: '#eef2ff', color: 'primary.main', width: 54, height: 54 }}><EditRounded/></Avatar><Typography fontWeight={750}>Выберите кампанию</Typography><Typography variant="body2" color="text.secondary">или создайте новую, чтобы начать</Typography></Stack></Card>}
      </Box>
    </Container>
    <Dialog open={createOpen} onClose={() => !loading && setCreateOpen(false)} fullWidth maxWidth="sm"><DialogTitle fontWeight={800}>Новая кампания</DialogTitle><DialogContent><Typography variant="body2" color="text.secondary" sx={{ mb: 2.2 }}>Создадим два потока: Google для выбранного GEO и оффер для остальных посетителей.</Typography><Stack spacing={2}><TextField autoFocus label="Название кампании" value={name} onChange={e => setName(e.target.value)} fullWidth/><Autocomplete<Country> options={countries} value={country} onChange={(_, value) => { if (value) setCountry(value) }} autoHighlight getOptionLabel={item => `${item.code} — ${item.name}`} isOptionEqualToValue={(a, b) => a.code === b.code} renderOption={(props, option) => <Box component="li" {...props} key={option.code} sx={{ display: 'flex', alignItems: 'center', gap: 1.2 }}><Typography component="span" sx={{ fontSize: 22, lineHeight: 1 }}>{option.flag}</Typography><Typography component="span" fontWeight={700} sx={{ minWidth: 32 }}>{option.code}</Typography><Typography component="span">{option.name}</Typography></Box>} renderInput={params => <TextField {...params} label="Страна / GEO" placeholder="Начните вводить название страны" helperText="Поиск по названию или ISO-коду" InputProps={{ ...params.InputProps, startAdornment: <>{country.flag}<Box component="span" sx={{ ml: 1 }}>{params.InputProps.startAdornment}</Box></> }}/>} /><Autocomplete options={offers} value={createOffer} onChange={(_, value) => setCreateOffer(value)} inputValue={query} onInputChange={(_, value) => setQuery(value)} getOptionLabel={o => `${o.name} (#${o.id})`} isOptionEqualToValue={(a,b) => a.id === b.id} renderInput={params => <TextField {...params} label="Стартовый оффер" placeholder="Поиск по офферам"/>}/></Stack></DialogContent><DialogActions sx={{ px: 3, pb: 2.5 }}><Button onClick={() => setCreateOpen(false)} disabled={loading}>Отмена</Button><Button variant="contained" onClick={() => void create()} disabled={loading || !name.trim() || !createOffer} startIcon={loading ? <CircularProgress size={16} color="inherit"/> : <AddRounded/>}>Создать кампанию</Button></DialogActions></Dialog>
    <Dialog open={importOpen} onClose={() => !loading && setImportOpen(false)} fullWidth maxWidth="xs"><DialogTitle fontWeight={800}>Открыть кампанию Keitaro</DialogTitle><DialogContent><Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>Введите ID кампании. GEO и список офферов загрузятся из её потоков Keitaro.</Typography><TextField autoFocus fullWidth label="ID кампании Keitaro" type="number" value={importId} onChange={e => setImportId(e.target.value)} onKeyDown={e => { if (e.key === 'Enter') void importExisting() }}/></DialogContent><DialogActions sx={{ px: 3, pb: 2.5 }}><Button onClick={() => setImportOpen(false)} disabled={loading}>Отмена</Button><Button variant="contained" startIcon={loading ? <CircularProgress size={16} color="inherit"/> : <FileDownloadOutlined/>} onClick={() => void importExisting()} disabled={loading || !importId}>Загрузить кампанию</Button></DialogActions></Dialog>
    <Dialog open={editOpen} onClose={() => !loading && setEditOpen(false)} fullWidth maxWidth="sm"><DialogTitle fontWeight={800}>Редактировать кампанию</DialogTitle><DialogContent><Typography variant="body2" color="text.secondary" sx={{ mb: 2.2 }}>Изменения будут сохранены в приложении и синхронизированы с Keitaro.</Typography><Stack spacing={2}><TextField autoFocus label="Название кампании" value={editName} onChange={e => setEditName(e.target.value)} fullWidth/><Autocomplete<Country> options={countries} value={editCountry} onChange={(_, value) => { if (value) setEditCountry(value) }} autoHighlight getOptionLabel={item => `${item.code} — ${item.name}`} isOptionEqualToValue={(a, b) => a.code === b.code} renderOption={(props, option) => <Box component="li" {...props} key={option.code} sx={{ display: 'flex', alignItems: 'center', gap: 1.2 }}><Typography component="span" sx={{ fontSize: 22, lineHeight: 1 }}>{option.flag}</Typography><Typography component="span" fontWeight={700} sx={{ minWidth: 32 }}>{option.code}</Typography><Typography component="span">{option.name}</Typography></Box>} renderInput={params => <TextField {...params} label="Страна / GEO" placeholder="Начните вводить название страны" helperText="Поиск по названию или ISO-коду"/>}/></Stack></DialogContent><DialogActions sx={{ px: 3, pb: 2.5 }}><Button onClick={() => setEditOpen(false)} disabled={loading}>Отмена</Button><Button variant="contained" onClick={() => void saveCampaign()} disabled={loading || !editName.trim()} startIcon={loading ? <CircularProgress size={16} color="inherit"/> : <EditRounded/>}>Сохранить</Button></DialogActions></Dialog>
  </Box>
}
