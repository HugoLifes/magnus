import 'package:get_it/get_it.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../../features/agents/presentation/cubit/agents_cubit.dart';
import '../../features/chat/presentation/cubit/chat_cubit.dart';
import '../../features/models/data/datasources/magnus_remote_datasource.dart';
import '../../features/models/data/repositories/magnus_repository_impl.dart';
import '../../features/models/domain/repositories/magnus_repository.dart';
import '../../features/models/domain/usecases.dart';
import '../../features/models/presentation/bloc/models_bloc.dart';
import '../../features/models/presentation/cubit/catalog_cubit.dart';
import '../../features/models/presentation/cubit/overview_cubit.dart';
import '../../features/rag/presentation/cubit/rag_cubit.dart';
import '../../features/resources/presentation/cubit/system_cubit.dart';
import '../../features/settings/presentation/cubit/settings_cubit.dart';
import '../network/dio_client.dart';
import '../network/magnus_api.dart';

final sl = GetIt.instance;

/// Registra todo el grafo de dependencias. Llamar una vez en `main()` antes de
/// runApp. El orden importa: externos -> red -> data -> domain -> presentación.
Future<void> initDependencies() async {
  // Externos
  final prefs = await SharedPreferences.getInstance();
  sl.registerSingleton<SharedPreferences>(prefs);

  // Red (singleton: una sola instancia de Dio compartida y reconfigurable)
  sl.registerSingleton<DioClient>(DioClient());
  sl.registerLazySingleton<MagnusApi>(() => MagnusApi(sl()));

  // Data
  sl.registerLazySingleton<MagnusRemoteDataSource>(() => MagnusRemoteDataSource(sl()));
  sl.registerLazySingleton<MagnusRepository>(() => MagnusRepositoryImpl(sl()));

  // Domain (casos de uso)
  sl.registerLazySingleton(() => GetHardware(sl()));
  sl.registerLazySingleton(() => GetModels(sl()));
  sl.registerLazySingleton(() => CheckCompatibility(sl()));
  sl.registerLazySingleton(() => GetQuantMatrix(sl()));

  // Presentación
  sl.registerFactory(() => ModelsBloc(
        getHardware: sl(),
        getModels: sl(),
        getQuantMatrix: sl(),
      ));
  sl.registerLazySingleton(() => SettingsCubit(sl(), sl()));
  // Singletons: el chat en curso, las descargas y las ejecuciones siguen vivos
  // al cambiar de sección (cada shell reconstruye la página al navegar).
  sl.registerLazySingleton(() => ChatCubit(sl()));
  sl.registerLazySingleton(() => CatalogCubit(sl()));
  sl.registerLazySingleton(() => RagCubit(sl()));
  sl.registerLazySingleton(() => AgentsCubit(sl()));
  sl.registerLazySingleton(() => OverviewCubit(sl()));
  // Factory: la telemetría solo se consulta mientras Recursos está abierta.
  sl.registerFactory(() => SystemCubit(sl()));
}
