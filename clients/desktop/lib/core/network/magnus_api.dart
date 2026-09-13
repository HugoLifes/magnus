import 'dart:async';
import 'dart:convert';

import 'package:dio/dio.dart';
import 'package:web_socket_channel/web_socket_channel.dart';

import '../error/failures.dart';
import 'api_models.dart';
import 'dio_client.dart';

/// Cliente tipado de la API del daemon: HTTP para lo normal, NDJSON para las
/// operaciones con progreso (descargas, agentes) y WebSocket para el chat.
///
/// Comparte el [DioClient] de la app, así un cambio de URL en Ajustes vale para
/// todo sin reconstruir nada.
class MagnusApi {
  MagnusApi(this._client);
  final DioClient _client;

  Dio get _dio => _client.dio;

  /// Operaciones que calculan (cargar un modelo, indexar documentos) pueden
  /// tardar minutos en un Jetson; el timeout por defecto es de 20 s.
  static final _long = Options(receiveTimeout: const Duration(minutes: 15));

  // ------------------------------------------------------------------ base

  Failure _map(DioException e) {
    if (e.type == DioExceptionType.connectionError ||
        e.type == DioExceptionType.connectionTimeout) {
      return ConnectionFailure(
          'No se pudo conectar a ${_client.baseUrl}. ¿Está corriendo `magnus serve`?');
    }
    if (e.type == DioExceptionType.receiveTimeout) {
      return const ServerFailure('El daemon tardó demasiado en responder.');
    }
    final data = e.response?.data;
    final detail = data is Map ? data['detail'] : null;
    return ServerFailure(detail?.toString() ?? 'Error ${e.response?.statusCode ?? ''} del daemon.');
  }

  Future<Map<String, dynamic>> _call(
      Future<Response<dynamic>> Function() request) async {
    try {
      final res = await request();
      final data = res.data;
      return data is Map ? data.cast<String, dynamic>() : <String, dynamic>{};
    } on DioException catch (e) {
      throw _map(e);
    } on Failure {
      rethrow;
    } catch (_) {
      throw const ParseFailure();
    }
  }

  Future<Map<String, dynamic>> _get(String path, [Map<String, dynamic>? query]) =>
      _call(() => _dio.get(path, queryParameters: query));

  Future<Map<String, dynamic>> _post(String path, [Object? body, Options? options]) =>
      _call(() => _dio.post(path, data: body, options: options));

  Future<Map<String, dynamic>> _put(String path, Object body) =>
      _call(() => _dio.put(path, data: body));

  Future<Map<String, dynamic>> _delete(String path) => _call(() => _dio.delete(path));

  List<Map<String, dynamic>> _list(Map<String, dynamic> body, String key) =>
      (body[key] as List? ?? const []).map((e) => (e as Map).cast<String, dynamic>()).toList();

  /// Respuesta NDJSON: un objeto JSON por línea, a medida que llega.
  Stream<Map<String, dynamic>> _ndjson(String path, [Object? body]) async* {
    final Response<ResponseBody> res;
    try {
      res = await _dio.post<ResponseBody>(
        path,
        data: body,
        options: Options(responseType: ResponseType.stream, receiveTimeout: const Duration(hours: 3)),
      );
    } on DioException catch (e) {
      throw _map(e);
    }
    final lines = res.data!.stream
        .cast<List<int>>()
        .transform(utf8.decoder)
        .transform(const LineSplitter());
    await for (final line in lines) {
      if (line.trim().isEmpty) continue;
      yield (jsonDecode(line) as Map).cast<String, dynamic>();
    }
  }

  // ------------------------------------------------------ plataforma y sistema

  Future<HealthInfo> health() async => HealthInfo.fromJson(await _get('/health'));

  Future<PlatformInfo> platform() async => PlatformInfo.fromJson(await _get('/platform'));

  Future<SystemSample> system() async => SystemSample.fromJson(await _get('/system'));

  Future<UsageSummary> usage() async => UsageSummary.fromJson(await _get('/usage'));

  // ---------------------------------------------------------------- modelos

  Future<CatalogInfo> catalog({String? capability}) async => CatalogInfo.fromJson(
      await _get('/catalog', capability == null ? null : {'capability': capability}));

  Future<List<LocalModel>> localModels() async =>
      _list(await _get('/models/local'), 'models').map(LocalModel.fromJson).toList();

  Future<List<LoadedModel>> loadedModels() async =>
      _list(await _get('/models/loaded'), 'loaded').map(LoadedModel.fromJson).toList();

  Future<LoadedModel> loadModel(String id, {bool force = false}) async => LoadedModel.fromJson(
      await _post('/models/$id/load', {'pull_if_missing': false, 'force': force}, _long));

  Future<void> unloadModel(String id) => _post('/models/$id/unload', {}, _long);

  Future<void> deleteModel(String id) => _delete('/models/$id');

  Stream<PullProgress> pullModel(String id) =>
      _ndjson('/models/$id/pull').map(PullProgress.fromJson);

  // ------------------------------------------------------------------- chat

  /// Un turno de chat por WebSocket. Emite los eventos del daemon (`start`,
  /// `thinking`, `token`, `done`, `error`) y termina con `done` o `error`.
  Stream<Map<String, dynamic>> chatTurn(Map<String, dynamic> request) async* {
    final base = Uri.parse(_client.baseUrl);
    final token = _client.token;
    // Los WebSocket no llevan las cabeceras de Dio: el token va en la URL.
    final uri = base.replace(
      scheme: base.scheme == 'https' ? 'wss' : 'ws',
      path: '/chat',
      queryParameters: token == null ? null : {'token': token},
    );
    final channel = WebSocketChannel.connect(uri);
    try {
      await channel.ready;
    } catch (_) {
      throw ConnectionFailure('No se pudo abrir el chat en $uri. ¿Está corriendo el daemon?');
    }
    channel.sink.add(jsonEncode(request));
    try {
      await for (final raw in channel.stream) {
        final event = (jsonDecode(raw as String) as Map).cast<String, dynamic>();
        yield event;
        if (event['type'] == 'done' || event['type'] == 'error') break;
      }
    } finally {
      await channel.sink.close();
    }
  }

  Future<List<ConversationInfo>> conversations() async =>
      _list(await _get('/conversations'), 'conversations').map(ConversationInfo.fromJson).toList();

  Future<List<StoredMessage>> conversationMessages(String id) async =>
      _list(await _get('/conversations/$id'), 'messages').map(StoredMessage.fromJson).toList();

  Future<void> deleteConversation(String id) => _delete('/conversations/$id');

  // ------------------------------------------------------ documentos y memoria

  Future<List<CollectionInfo>> collections() async =>
      _list(await _get('/rag/collections'), 'collections').map(CollectionInfo.fromJson).toList();

  Future<void> createCollection(String name,
          {String embeddingModel = 'nomic-embed-text', int chunkChars = 1000, int overlapChars = 150}) =>
      _post('/rag/collections', {
        'name': name,
        'embedding_model': embeddingModel,
        'chunk_chars': chunkChars,
        'overlap_chars': overlapChars,
      });

  Future<void> deleteCollection(String name) => _delete('/rag/collections/$name');

  Future<List<DocumentInfo>> documents(String collection) async =>
      _list(await _get('/rag/collections/$collection/documents'), 'documents')
          .map(DocumentInfo.fromJson)
          .toList();

  Future<IngestResult> ingest(String collection, {List<String> paths = const [], String? text}) async =>
      IngestResult.fromJson(await _post(
          '/rag/ingest',
          {'collection': collection, 'paths': paths, if (text != null) 'text': text},
          _long));

  Future<List<SearchHit>> search(String collection, String query, {int k = 5}) async =>
      _list(await _post('/rag/search', {'collection': collection, 'query': query, 'k': k}, _long),
              'hits')
          .map(SearchHit.fromJson)
          .toList();

  Future<List<MemoryItem>> memories() async =>
      _list(await _get('/memory'), 'memories').map(MemoryItem.fromJson).toList();

  Future<void> addMemory(String text) => _post('/memory', {'text': text}, _long);

  Future<void> deleteMemory(int id) => _delete('/memory/$id');

  // --------------------------------------------------------- skills y agentes

  Future<(List<SkillInfo>, Map<String, String>)> skills() async {
    final body = await _get('/skills');
    final errors = (body['errors'] as Map? ?? const {}).map((k, v) => MapEntry('$k', '$v'));
    return (_list(body, 'skills').map(SkillInfo.fromJson).toList(), errors);
  }

  Future<SkillInfo> skill(String name) async => SkillInfo.fromJson(await _get('/skills/$name'));

  Future<void> saveSkill(String name,
          {required String description, required String body, List<String> triggers = const []}) =>
      _put('/skills/$name', {'description': description, 'body': body, 'triggers': triggers});

  Future<void> deleteSkill(String name) => _delete('/skills/$name');

  Future<List<ToolInfo>> tools() async =>
      _list(await _get('/tools'), 'tools').map(ToolInfo.fromJson).toList();

  Future<(List<AgentInfo>, Map<String, String>)> agents() async {
    final body = await _get('/agents');
    final errors = (body['errors'] as Map? ?? const {}).map((k, v) => MapEntry('$k', '$v'));
    return (_list(body, 'agents').map(AgentInfo.fromJson).toList(), errors);
  }

  Future<void> saveAgent(AgentInfo agent) => _put('/agents/${agent.name}', agent.toBody());

  Future<void> deleteAgent(String name) => _delete('/agents/$name');

  /// Eventos de un agente: `start`, `tool_call`, `tool_result`, `answer`, `done` o `error`.
  Stream<Map<String, dynamic>> runAgent(String name, String message, {String? model}) =>
      _ndjson('/agents/$name/run', {'message': message, if (model != null) 'model': model});

  // ---------------------------------------------------------------- ajustes

  Future<DaemonSettings> daemonSettings() async => DaemonSettings.fromJson(await _get('/settings'));

  Future<DaemonSettings> updateDaemonSettings(Map<String, dynamic> changes) async =>
      DaemonSettings.fromJson(await _put('/settings', changes));
}
