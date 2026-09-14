import 'package:flutter/material.dart'
    show Material, Colors, TextField, InputDecoration, OutlineInputBorder, SelectableText;
import 'package:flutter/widgets.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../../../core/network/api_models.dart';
import '../../../../core/theme/brand.dart';
import '../../../../core/theme/magnus_theme.dart';
import '../../../../shared/widgets/forms.dart';
import '../../../../shared/widgets/magnus_kit.dart';
import '../../../../shared/widgets/ui.dart';
import '../cubit/cloud_cubit.dart';

/// Nube: qué hacer cuando tu equipo no alcanza. El orden de la página es el
/// orden de la promesa — primero tu red, luego tu propia clave, y Magnus Cloud
/// con créditos — y nada se activa solo: el chat elige dónde corre cada turno.
class CloudPage extends StatefulWidget {
  const CloudPage({super.key});
  @override
  State<CloudPage> createState() => _CloudPageState();
}

class _CloudPageState extends State<CloudPage> {
  @override
  void initState() {
    super.initState();
    context.read<CloudCubit>().load();
  }

  @override
  Widget build(BuildContext context) {
    return BlocBuilder<CloudCubit, CloudState>(
      builder: (context, state) {
        final cubit = context.read<CloudCubit>();
        return PageScaffold(
          maxWidth: 1180,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              _Hero(state: state),
              if (state.error != null) ...[
                const SizedBox(height: 14),
                InlineNotice(state.error!, onClose: cubit.dismiss),
              ],
              if (state.notice != null) ...[
                const SizedBox(height: 14),
                InlineNotice(state.notice!, kind: NoticeKind.info, onClose: cubit.dismiss),
              ],
              const SizedBox(height: 30),
              const _SectionTitle(
                icon: LucideIcons.sparkles,
                title: 'Magnus Cloud',
                subtitle: 'Modelos abiertos en hardware NVIDIA propio. Pagas con créditos; '
                    'nada se guarda ni se usa para entrenar.',
              ),
              state.cloud == null ? const _CloudConnect() : _CloudWallet(state: state),
              const SizedBox(height: 34),
              const _SectionTitle(
                icon: LucideIcons.keyRound,
                title: 'Con tu propia clave',
                subtitle: 'Tu cuenta, tus términos. Magnus solo enruta y guarda la clave en el '
                    'llavero del sistema.',
              ),
              _KeyProviders(state: state),
              const SizedBox(height: 34),
              const _SectionTitle(
                icon: LucideIcons.network,
                title: 'Tus servidores',
                subtitle: 'vLLM en otro equipo tuyo — un DGX Spark, una PC con RTX, un servidor. '
                    'Tus datos no salen de tu red.',
              ),
              _Servers(state: state),
            ],
          ),
        );
      },
    );
  }
}

// ---------------------------------------------------------------------------
// Héroe
// ---------------------------------------------------------------------------

class _Hero extends StatelessWidget {
  const _Hero({required this.state});
  final CloudState state;

  @override
  Widget build(BuildContext context) {
    final t = MagnusTheme.of(context);
    final account = state.account;
    return AuroraBackdrop(
      child: Container(
        padding: const EdgeInsets.fromLTRB(30, 30, 30, 28),
        decoration: BoxDecoration(
          border: Border.all(color: t.stroke),
          borderRadius: BorderRadius.circular(t.radiusLg),
        ),
        child: LayoutBuilder(builder: (context, c) {
          final wide = c.maxWidth > 760;
          final copy = Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text('NUNCA TE QUEDAS SIN IA',
                  style: t.small.copyWith(letterSpacing: 1.6, fontWeight: FontWeight.w700, color: t.accent)),
              const SizedBox(height: 10),
              Text('Tu equipo primero.\nLa nube, solo si tú quieres.',
                  style: t.display.copyWith(fontSize: 32, height: 1.1, letterSpacing: -0.8)),
              const SizedBox(height: 12),
              ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 520),
                child: Text(
                  'Cuando un modelo no cabe en tu memoria, Magnus te ofrece tres salidas en este '
                  'orden. Tú eliges en cada conversación y cada respuesta dice dónde corrió.',
                  style: t.body.copyWith(color: t.textMuted, fontSize: 14.5),
                ),
              ),
              const SizedBox(height: 20),
              const Wrap(
                spacing: 10,
                runSpacing: 10,
                crossAxisAlignment: WrapCrossAlignment.center,
                children: [
                  _Step(n: 1, label: 'Este equipo', icon: LucideIcons.cpu, color: Brand.teal),
                  _Arrow(),
                  _Step(n: 2, label: 'Tu red', icon: LucideIcons.network, color: Brand.sky),
                  _Arrow(),
                  _Step(n: 3, label: 'La nube', icon: LucideIcons.cloud, color: Brand.lilac),
                ],
              ),
            ],
          );
          final ring = Column(mainAxisSize: MainAxisSize.min, children: [
            CreditRing(
              credits: account?.balanceCredits ?? 0,
              reference: _ringReference(state),
            ),
            const SizedBox(height: 10),
            Text(
              account == null ? 'Magnus Cloud sin conectar' : '≈ \$${account.balanceUsd.toStringAsFixed(2)} USD',
              style: t.small.copyWith(color: t.textMuted),
            ),
          ]);
          return wide
              ? Row(children: [Expanded(child: copy), const SizedBox(width: 24), ring])
              : Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  copy,
                  const SizedBox(height: 22),
                  Center(child: ring),
                ]);
        }),
      ),
    );
  }

  /// Referencia del anillo: el paquete más chico que cubre el saldo, o el bono mensual.
  static double _ringReference(CloudState s) {
    final balance = s.account?.balanceCredits ?? 0;
    final base = (s.account?.freeMonthlyCredits ?? 100).toDouble();
    final sizes = [for (final p in s.packs) p.credits.toDouble()]..sort();
    for (final size in sizes) {
      if (size >= balance) return size;
    }
    return balance > base ? balance : base;
  }
}

class _Step extends StatelessWidget {
  const _Step({required this.n, required this.label, required this.icon, required this.color});
  final int n;
  final String label;
  final IconData icon;
  final Color color;

  @override
  Widget build(BuildContext context) {
    final t = MagnusTheme.of(context);
    return Container(
      padding: const EdgeInsets.fromLTRB(6, 6, 14, 6),
      decoration: BoxDecoration(
        color: t.surface,
        borderRadius: BorderRadius.circular(30),
        border: Border.all(color: color.withValues(alpha: 0.45)),
      ),
      child: Row(mainAxisSize: MainAxisSize.min, children: [
        Container(
          width: 26,
          height: 26,
          alignment: Alignment.center,
          decoration: BoxDecoration(color: color.withValues(alpha: 0.18), shape: BoxShape.circle),
          child: Text('$n', style: TextStyle(color: color, fontWeight: FontWeight.w800, fontSize: 12.5)),
        ),
        const SizedBox(width: 8),
        Icon(icon, size: 15, color: color),
        const SizedBox(width: 6),
        Text(label, style: t.body.copyWith(fontWeight: FontWeight.w600)),
      ]),
    );
  }
}

class _Arrow extends StatelessWidget {
  const _Arrow();
  @override
  Widget build(BuildContext context) =>
      Icon(LucideIcons.chevronRight, size: 16, color: MagnusTheme.of(context).textFaint);
}

class _SectionTitle extends StatelessWidget {
  const _SectionTitle({required this.icon, required this.title, required this.subtitle});
  final IconData icon;
  final String title;
  final String subtitle;

  @override
  Widget build(BuildContext context) =>
      SectionHeader(title: title, subtitle: subtitle, icon: icon);
}

// ---------------------------------------------------------------------------
// Magnus Cloud
// ---------------------------------------------------------------------------

class _CloudConnect extends StatefulWidget {
  const _CloudConnect();
  @override
  State<_CloudConnect> createState() => _CloudConnectState();
}

class _CloudConnectState extends State<_CloudConnect> {
  final _url = TextEditingController();
  final _key = TextEditingController();

  @override
  void dispose() {
    _url.dispose();
    _key.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final t = MagnusTheme.of(context);
    final state = context.watch<CloudCubit>().state;
    final preset = state.preset('magnus-cloud');
    if (_url.text.isEmpty && preset != null) _url.text = preset.baseUrl;
    return SpotlightCard(
      padding: const EdgeInsets.all(22),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text('Conecta tu cuenta', style: t.h1),
        const SizedBox(height: 4),
        Text('Recibes 100 créditos gratis cada mes. La clave te la da tu asesor Magnus al abrir '
            'la cuenta (empieza con mgk_).', style: t.small),
        const SizedBox(height: 16),
        LayoutBuilder(builder: (context, c) {
          final fields = [
            _Labeled('Servidor', MagnusTextField(controller: _url, hint: 'https://…/v1', mono: true)),
            _Labeled('Clave', _SecretField(controller: _key, hint: 'mgk_…')),
          ];
          return c.maxWidth > 700
              ? Row(crossAxisAlignment: CrossAxisAlignment.end, children: [
                  Expanded(child: fields[0]),
                  const SizedBox(width: 12),
                  Expanded(child: fields[1]),
                ])
              : Column(children: [fields[0], const SizedBox(height: 12), fields[1]]);
        }),
        const SizedBox(height: 16),
        GlowButton(
          label: 'Conectar Magnus Cloud',
          icon: LucideIcons.plugZap,
          busy: state.busy == 'connect:magnus-cloud',
          onTap: () => context.read<CloudCubit>().connect('magnus-cloud',
              kind: 'magnus-cloud', baseUrl: _url.text.trim(), apiKey: _key.text.trim()),
        ),
      ]),
    );
  }
}

class _CloudWallet extends StatefulWidget {
  const _CloudWallet({required this.state});
  final CloudState state;
  @override
  State<_CloudWallet> createState() => _CloudWalletState();
}

class _CloudWalletState extends State<_CloudWallet> {
  final _code = TextEditingController();

  @override
  void dispose() {
    _code.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final t = MagnusTheme.of(context);
    final state = widget.state;
    final cubit = context.read<CloudCubit>();
    final account = state.account;

    final wallet = SpotlightCard(
      glow: Brand.amber,
      padding: const EdgeInsets.all(20),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Expanded(child: Text(account?.name ?? 'Tu saldo', style: t.h1)),
          _IconAction(LucideIcons.refreshCw, 'Actualizar saldo', cubit.refreshAccount),
        ]),
        const SizedBox(height: 4),
        Text('+${account?.freeMonthlyCredits ?? 100} créditos gratis cada mes', style: t.small),
        const SizedBox(height: 16),
        const FieldLabel('Canjear un vale', hint: 'Formato MAG-XXXX-XXXX-XXXX'),
        MagnusTextField(controller: _code, hint: 'MAG-', mono: true, onSubmitted: (_) => _redeem()),
        const SizedBox(height: 10),
        GlowButton(
          label: 'Canjear vale',
          icon: LucideIcons.ticket,
          variant: GlowVariant.savings,
          expand: true,
          busy: state.busy == 'redeem',
          onTap: _redeem,
        ),
        if (account != null && account.history.isNotEmpty) ...[
          const SizedBox(height: 18),
          Text('MOVIMIENTOS', style: t.small.copyWith(fontSize: 10.5, letterSpacing: 1.2, color: t.textFaint)),
          const SizedBox(height: 6),
          for (final m in account.history.take(6)) _Movement(m),
        ],
      ]),
    );

    final packs = state.packs.isEmpty
        ? GlassCard(
            child: Text('Cargando paquetes…', style: t.small),
          )
        : Wrap(
            spacing: 14,
            runSpacing: 14,
            children: [for (final p in state.packs) SizedBox(width: 250, child: _PackCard(p))],
          );

    return LayoutBuilder(builder: (context, c) {
      if (c.maxWidth < 900) {
        return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          wallet,
          const SizedBox(height: 16),
          packs,
        ]);
      }
      return Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
        SizedBox(width: 320, child: wallet),
        const SizedBox(width: 18),
        Expanded(child: packs),
      ]);
    });
  }

  void _redeem() {
    context.read<CloudCubit>().redeem(_code.text);
    _code.clear();
  }
}

class _Movement extends StatelessWidget {
  const _Movement(this.m);
  final CreditMovement m;

  @override
  Widget build(BuildContext context) {
    final t = MagnusTheme.of(context);
    final (icon, label) = switch (m.kind) {
      'grant' => (LucideIcons.gift, 'Bono mensual'),
      'topup' => (LucideIcons.ticket, 'Vale ${m.meta['paquete'] ?? ''}'),
      'debit' => (LucideIcons.messageCircle,
          '${m.meta['modelo'] ?? 'Uso'} · ${m.meta['tokens_out'] ?? '?'} tok'),
      _ => (LucideIcons.slidersHorizontal, 'Ajuste'),
    };
    final positive = m.credits >= 0;
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 5),
      child: Row(children: [
        Icon(icon, size: 14, color: t.textFaint),
        const SizedBox(width: 8),
        Expanded(child: Text(label, maxLines: 1, overflow: TextOverflow.ellipsis, style: t.small)),
        Text('${positive ? '+' : ''}${m.credits.toStringAsFixed(m.credits.abs() < 10 ? 2 : 0)}',
            style: t.mono.copyWith(
                fontSize: 12, color: positive ? Brand.amber : t.textMuted, fontWeight: FontWeight.w600)),
      ]),
    );
  }
}

class _PackCard extends StatelessWidget {
  const _PackCard(this.pack);
  final CreditPack pack;

  @override
  Widget build(BuildContext context) {
    final t = MagnusTheme.of(context);
    return SpotlightCard(
      featured: pack.featured,
      padding: const EdgeInsets.all(20),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Expanded(child: Text(pack.name, style: t.h1.copyWith(fontSize: 21))),
          if (pack.featured) Pill('Más elegido', color: t.accent, icon: LucideIcons.star),
        ]),
        const SizedBox(height: 4),
        Text(pack.tagline, style: t.small, maxLines: 2),
        const SizedBox(height: 16),
        Row(crossAxisAlignment: CrossAxisAlignment.end, children: [
          Text('\$${pack.priceUsd.toStringAsFixed(0)}',
              style: t.display.copyWith(fontSize: 38, height: 1, letterSpacing: -1.2)),
          const SizedBox(width: 6),
          Padding(padding: const EdgeInsets.only(bottom: 5), child: Text('USD', style: t.small)),
        ]),
        const SizedBox(height: 10),
        Text('${_thousands(pack.credits)} créditos',
            style: t.body.copyWith(fontWeight: FontWeight.w700)),
        if (pack.approxTokens != null)
          Text('≈ ${_millions(pack.approxTokens!)} tokens de ${pack.referenceModel}', style: t.small),
        const SizedBox(height: 10),
        if (pack.bonusPct > 0)
          Pill('+${pack.bonusPct}% de regalo', color: Brand.amber, icon: LucideIcons.gift)
        else
          Pill('Sin caducidad', color: t.textMuted, icon: LucideIcons.infinity),
        const SizedBox(height: 16),
        GlowButton(
          label: 'Quiero ${pack.name}',
          variant: pack.featured ? GlowVariant.primary : GlowVariant.secondary,
          expand: true,
          // Pasarela de pago pendiente de elegir (Mercado Pago o Stripe). Mientras,
          // el paquete se compra como vale con un asesor y se canjea aquí.
          onTap: () => context.read<CloudCubit>().showNotice(
              'Pide el vale ${pack.name} a tu asesor Magnus (\$${pack.priceUsd.toStringAsFixed(0)} USD) '
              'y canjéalo en «Canjear un vale». El pago en línea llega pronto.'),
        ),
      ]),
    );
  }

  static String _thousands(int n) =>
      n.toString().replaceAllMapped(RegExp(r'\B(?=(\d{3})+(?!\d))'), (_) => ',');

  static String _millions(int tokens) =>
      tokens >= 1000000 ? '${(tokens / 1e6).toStringAsFixed(tokens >= 1e7 ? 0 : 1)} M' : '${tokens ~/ 1000}K';
}

// ---------------------------------------------------------------------------
// Con tu propia clave
// ---------------------------------------------------------------------------

class _KeyProviders extends StatelessWidget {
  const _KeyProviders({required this.state});
  final CloudState state;

  static const _kinds = ['nvidia', 'groq', 'openrouter'];

  @override
  Widget build(BuildContext context) {
    final presets = [for (final k in _kinds) state.preset(k)].whereType<ProviderPreset>().toList();
    if (presets.isEmpty) {
      return GlassCard(child: Text('Cargando proveedores…', style: MagnusTheme.of(context).small));
    }
    return LayoutBuilder(builder: (context, c) {
      final columns = c.maxWidth > 1000 ? 3 : (c.maxWidth > 640 ? 2 : 1);
      final width = (c.maxWidth - 14 * (columns - 1)) / columns;
      return Wrap(
        spacing: 14,
        runSpacing: 14,
        children: [
          for (final p in presets)
            SizedBox(width: width, child: _KeyProviderCard(preset: p, state: state)),
        ],
      );
    });
  }
}

class _KeyProviderCard extends StatefulWidget {
  const _KeyProviderCard({required this.preset, required this.state});
  final ProviderPreset preset;
  final CloudState state;
  @override
  State<_KeyProviderCard> createState() => _KeyProviderCardState();
}

class _KeyProviderCardState extends State<_KeyProviderCard> {
  final _key = TextEditingController();

  @override
  void dispose() {
    _key.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final t = MagnusTheme.of(context);
    final cubit = context.read<CloudCubit>();
    final preset = widget.preset;
    final id = preset.kind;
    final info = widget.state.byId(id);
    final connected = info != null && info.hasKey;
    final test = widget.state.tests[id];
    final busy = widget.state.busy;

    return SpotlightCard(
      padding: const EdgeInsets.all(18),
      glow: preset.kind == 'nvidia' ? Brand.teal : null,
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Expanded(child: Text(preset.label, style: t.h2.copyWith(fontSize: 16.5))),
          connected
              ? const Pill('Conectado', color: Brand.teal, icon: LucideIcons.check)
              : Pill('Sin conectar', color: t.textFaint),
        ]),
        const SizedBox(height: 6),
        Text(preset.description, style: t.small),
        if (preset.notice.isNotEmpty) ...[
          const SizedBox(height: 12),
          _Notice(preset.notice, strong: preset.kind == 'nvidia'),
        ],
        const SizedBox(height: 14),
        _SecretField(controller: _key, hint: connected ? 'Clave guardada · escribe otra para cambiarla' : 'Pega tu clave'),
        if (preset.keyUrl != null) ...[
          const SizedBox(height: 6),
          Row(children: [
            Icon(LucideIcons.externalLink, size: 12, color: t.textFaint),
            const SizedBox(width: 5),
            Flexible(
              child: Material(
                color: Colors.transparent,
                child: SelectableText('Consigue tu clave en ${preset.keyUrl}',
                    style: t.small.copyWith(fontSize: 11.5)),
              ),
            ),
          ]),
        ],
        if (test != null) ...[
          const SizedBox(height: 10),
          test.ok
              ? Text('✓ ${test.models} modelos · ${test.sample.take(2).join(', ')}',
                  maxLines: 2, overflow: TextOverflow.ellipsis,
                  style: t.small.copyWith(color: Brand.teal))
              : InlineNotice(test.detail ?? 'No respondió.'),
        ],
        const SizedBox(height: 14),
        Wrap(spacing: 8, runSpacing: 8, children: [
          GlowButton(
            label: connected ? 'Cambiar clave' : 'Conectar',
            icon: LucideIcons.plugZap,
            dense: true,
            busy: busy == 'connect:$id',
            onTap: () {
              cubit.connect(id, kind: preset.kind, apiKey: _key.text.trim());
              _key.clear();
            },
          ),
          if (info != null) ...[
            GlowButton(
              label: 'Probar',
              icon: LucideIcons.activity,
              variant: GlowVariant.secondary,
              dense: true,
              busy: busy == 'test:$id',
              onTap: () => cubit.test(id),
            ),
            GlowButton(
              label: 'Quitar',
              icon: LucideIcons.trash2,
              variant: GlowVariant.secondary,
              dense: true,
              busy: busy == 'remove:$id',
              onTap: () => cubit.remove(id),
            ),
          ],
        ]),
      ]),
    );
  }
}

// ---------------------------------------------------------------------------
// Tus servidores
// ---------------------------------------------------------------------------

class _Servers extends StatefulWidget {
  const _Servers({required this.state});
  final CloudState state;
  @override
  State<_Servers> createState() => _ServersState();
}

class _ServersState extends State<_Servers> {
  final _name = TextEditingController();
  final _url = TextEditingController(text: 'http://192.168.1.');
  String _kind = 'vllm';

  @override
  void dispose() {
    _name.dispose();
    _url.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final t = MagnusTheme.of(context);
    final state = widget.state;
    final cubit = context.read<CloudCubit>();
    final id = _slug(_name.text);

    return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      for (final s in state.servers) ...[
        _ServerRow(server: s, state: state),
        const SizedBox(height: 10),
      ],
      GlassCard(
        padding: const EdgeInsets.all(18),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text('Agregar un servidor', style: t.h2),
          const SizedBox(height: 12),
          Wrap(spacing: 8, runSpacing: 8, children: [
            ChoiceChipX(label: 'vLLM', selected: _kind == 'vllm', onTap: () => setState(() => _kind = 'vllm')),
            ChoiceChipX(
                label: 'Compatible con OpenAI (LM Studio, llama.cpp)',
                selected: _kind == 'openai-compatible',
                onTap: () => setState(() => _kind = 'openai-compatible')),
          ]),
          const SizedBox(height: 12),
          LayoutBuilder(builder: (context, c) {
            final name = _Labeled('Nombre', MagnusTextField(controller: _name, hint: 'DGX Spark de la oficina'));
            final url = _Labeled('URL', MagnusTextField(controller: _url, hint: 'http://192.168.1.40:8000/v1', mono: true));
            return c.maxWidth > 700
                ? Row(children: [Expanded(child: name), const SizedBox(width: 12), Expanded(child: url)])
                : Column(children: [name, const SizedBox(height: 12), url]);
          }),
          const SizedBox(height: 14),
          GlowButton(
            label: 'Agregar y probar',
            icon: LucideIcons.plus,
            busy: state.busy == 'connect:$id',
            onTap: _name.text.trim().isEmpty && id.isEmpty
                ? null
                : () => cubit.connect(id.isEmpty ? 'servidor' : id,
                    kind: _kind, name: _name.text.trim(), baseUrl: _url.text.trim()),
          ),
        ]),
      ),
    ]);
  }

  static String _slug(String name) {
    final s = name.toLowerCase().replaceAll(RegExp(r'[^a-z0-9]+'), '-').replaceAll(RegExp(r'^-+|-+$'), '');
    return s.length > 40 ? s.substring(0, 40) : s;
  }
}

class _ServerRow extends StatelessWidget {
  const _ServerRow({required this.server, required this.state});
  final ProviderInfo server;
  final CloudState state;

  @override
  Widget build(BuildContext context) {
    final t = MagnusTheme.of(context);
    final cubit = context.read<CloudCubit>();
    final test = state.tests[server.id];
    return SpotlightCard(
      padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 14),
      glow: Brand.location(server.location),
      child: Row(children: [
        Icon(server.kind == 'vllm' ? LucideIcons.server : LucideIcons.plug, size: 18, color: t.textMuted),
        const SizedBox(width: 12),
        Expanded(
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Row(children: [
              Flexible(child: Text(server.name, style: t.h2, overflow: TextOverflow.ellipsis)),
              const SizedBox(width: 8),
              LocationChip(server.location),
            ]),
            const SizedBox(height: 2),
            Text(server.baseUrl, style: t.mono.copyWith(fontSize: 11.5, color: t.textFaint)),
            if (test != null)
              Padding(
                padding: const EdgeInsets.only(top: 4),
                child: Text(
                  test.ok ? '✓ ${test.models} modelos · ${test.sample.take(2).join(', ')}' : (test.detail ?? 'No respondió.'),
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                  style: t.small.copyWith(color: test.ok ? Brand.teal : Brand.rose),
                ),
              ),
          ]),
        ),
        const SizedBox(width: 10),
        GlowButton(
          label: 'Probar',
          icon: LucideIcons.activity,
          variant: GlowVariant.secondary,
          dense: true,
          busy: state.busy == 'test:${server.id}',
          onTap: () => cubit.test(server.id),
        ),
        const SizedBox(width: 8),
        _IconAction(LucideIcons.trash2, 'Quitar', () => cubit.remove(server.id)),
      ]),
    );
  }
}

// ---------------------------------------------------------------------------
// Piezas pequeñas
// ---------------------------------------------------------------------------

class _Labeled extends StatelessWidget {
  const _Labeled(this.label, this.child);
  final String label;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    final t = MagnusTheme.of(context);
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Text(label, style: t.small.copyWith(fontWeight: FontWeight.w600)),
      const SizedBox(height: 6),
      child,
    ]);
  }
}

/// Aviso de privacidad o de términos: coral si el usuario debe leerlo antes de conectar.
class _Notice extends StatelessWidget {
  const _Notice(this.text, {this.strong = false});
  final String text;
  final bool strong;

  @override
  Widget build(BuildContext context) {
    final t = MagnusTheme.of(context);
    final color = strong ? Brand.coral : Brand.lilac;
    return Container(
      padding: const EdgeInsets.all(10),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.10),
        borderRadius: BorderRadius.circular(t.radius),
        border: Border(left: BorderSide(color: color, width: 3)),
      ),
      child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Icon(strong ? LucideIcons.shieldAlert : LucideIcons.cloud, size: 14, color: color),
        const SizedBox(width: 8),
        Expanded(child: Text(text, style: t.small.copyWith(color: t.text, height: 1.4))),
      ]),
    );
  }
}

class _SecretField extends StatefulWidget {
  const _SecretField({required this.controller, required this.hint});
  final TextEditingController controller;
  final String hint;
  @override
  State<_SecretField> createState() => _SecretFieldState();
}

class _SecretFieldState extends State<_SecretField> {
  bool _visible = false;

  @override
  Widget build(BuildContext context) {
    final t = MagnusTheme.of(context);
    OutlineInputBorder border(Color c) => OutlineInputBorder(
          borderRadius: BorderRadius.circular(t.radius),
          borderSide: BorderSide(color: c),
        );
    return Material(
      color: Colors.transparent,
      child: TextField(
        controller: widget.controller,
        obscureText: !_visible,
        autocorrect: false,
        enableSuggestions: false,
        style: t.mono,
        decoration: InputDecoration(
          isDense: true,
          filled: true,
          fillColor: t.surfaceAlt,
          hintText: widget.hint,
          hintStyle: TextStyle(color: t.textFaint, fontSize: 13),
          border: border(t.stroke),
          enabledBorder: border(t.stroke),
          focusedBorder: border(t.accent),
          suffixIcon: GestureDetector(
            onTap: () => setState(() => _visible = !_visible),
            child: Icon(_visible ? LucideIcons.eyeOff : LucideIcons.eye, size: 16, color: t.textFaint),
          ),
        ),
      ),
    );
  }
}

class _IconAction extends StatelessWidget {
  const _IconAction(this.icon, this.tooltip, this.onTap);
  final IconData icon;
  final String tooltip;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final t = MagnusTheme.of(context);
    return Semantics(
      button: true,
      label: tooltip,
      child: MouseRegion(
        cursor: SystemMouseCursors.click,
        child: GestureDetector(
          onTap: onTap,
          child: Container(
            padding: const EdgeInsets.all(8),
            decoration: BoxDecoration(
              color: t.surfaceAlt,
              borderRadius: BorderRadius.circular(t.radius),
              border: Border.all(color: t.stroke),
            ),
            child: Icon(icon, size: 15, color: t.textMuted),
          ),
        ),
      ),
    );
  }
}
