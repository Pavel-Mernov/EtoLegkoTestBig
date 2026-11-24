import React from 'react'
import ReactDOM from 'react-dom/client'
import { CssBaseline, ThemeProvider, createTheme } from '@mui/material'
import App from './App'

const theme = createTheme({ palette: { mode: 'light', primary: { main: '#3b6df6' }, secondary: { main: '#7c62e8' }, background: { default: '#f5f7fb', paper: '#fff' }, success: { main: '#199b72' } }, shape: { borderRadius: 12 }, typography: { fontFamily: 'Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif', button: { textTransform: 'none', fontWeight: 650 } }, components: { MuiCard: { styleOverrides: { root: { border: '1px solid #e8ebf2', boxShadow: '0 8px 28px rgba(35, 47, 80, .045)' } } }, MuiButton: { styleOverrides: { root: { borderRadius: 9, paddingInline: 18 } } } } })

ReactDOM.createRoot(document.getElementById('root')!).render(<React.StrictMode><ThemeProvider theme={theme}><CssBaseline/><App/></ThemeProvider></React.StrictMode>)
