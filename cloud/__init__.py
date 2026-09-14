"""Magnus Cloud: vender inferencia con créditos desde cualquier equipo NVIDIA.

No es una nube ajena: es un gateway que se pone delante de un vLLM propio —un
B200, un DGX Spark, una PC con RTX— y cobra por tokens con saldo prepagado.
El mismo código sirve para Hugo (Magnus Cloud) y para un cliente Team que
quiere repartir la GPU de su oficina con cuotas.

- `packs`   — paquetes de créditos y precio por modelo.
- `ledger`  — saldo en SQLite: bono mensual gratis, recargas, cobros y vales.
- `gateway` — API compatible con OpenAI que valida saldo, reenvía a vLLM y cobra.
- `admin`   — CLI del operador: cuentas y vales.

Todo el dinero se lleva en enteros (milicréditos) para no arrastrar redondeos.
"""
