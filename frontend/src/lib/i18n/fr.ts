// French strings. Keys must exactly mirror en.ts -- the `Record<TranslationKey, string>`
// annotation makes a missing/extra key a type error at build time.
import type { TranslationKey } from './en';

export const fr: Record<TranslationKey, string> = {
	'layout.nav.dashboard': 'Tableau de bord',
	'layout.nav.newAnalysis': 'Nouvelle analyse',
	'layout.nav.logout': 'Se déconnecter',
	'layout.nav.login': 'Se connecter',
	'layout.nav.signup': "S'inscrire",
	'layout.footer.notice':
		"Outil de recherche — inférence uniquement, ce n'est pas un service diagnostique ou clinique. Consultez notre",
	'layout.footer.privacyLink': 'politique de confidentialité et de conservation des données',

	'home.title': "Inférence d'ascendance génétique, propulsée par Diet Network",
	'home.subtitle':
		"Téléversez votre fichier de génotypes VCF ou bgen et obtenez des prédictions d'ascendance grâce à l'ensemble Diet Network pré-entraîné du HussinLab — 15 modèles entraînés sur 1000 Genomes, couvrant 24 populations.",
	'home.cta.start': 'Démarrer une nouvelle analyse',
	'home.cta.createAccount': 'Créer un compte gratuit',
	'home.cta.login': 'Se connecter',
	'home.feature1.title': 'Utilisez vos propres génotypes',
	'home.feature1.prefix':
		'Accepte les fichiers .vcf, .vcf.gz et .bgen (avec un fichier .sample). Les génotypes doivent être harmonisés avec',
	'home.feature2.title': "Inférence asynchrone par ensemble de modèles",
	'home.feature2.body':
		'Chaque tâche exécute 15 modèles séquentiellement — généralement quelques minutes. Suivez l’état en direct depuis votre tableau de bord et recevez un courriel lorsque les résultats sont prêts.',
	'home.feature3.title': 'Confidentialité dès la conception',
	'home.feature3.prefix':
		'Les fichiers de génotypes bruts sont supprimés immédiatement après le succès de l’inférence. Tous les résultats sont automatiquement supprimés après 30 jours. Consultez notre',
	'home.feature3.privacyLink': 'politique de confidentialité',

	'auth.email': 'Courriel',
	'auth.password': 'Mot de passe',
	'auth.errorCaptcha': 'Veuillez compléter le test CAPTCHA.',
	'auth.errorGeneric': "Une erreur s'est produite. Veuillez réessayer.",

	'login.title': 'Connexion',
	'login.submit': 'Se connecter',
	'login.submitting': 'Connexion…',
	'login.noAccount': "Vous n'avez pas de compte ?",
	'login.signupLink': "S'inscrire",

	'signup.title': 'Créer votre compte',
	'signup.doneNoticePrefix': 'Consultez',
	'signup.doneNoticeSuffix':
		'pour un lien de vérification. Vous devez vérifier votre courriel avant de pouvoir vous connecter ou téléverser des données.',
	'signup.passwordHint': 'Au moins 12 caractères, avec majuscule, minuscule et un chiffre.',
	'signup.consentPrefix': 'Je consens au traitement de mes données génétiques tel que décrit dans la',
	'signup.consentLink': 'politique de confidentialité',
	'signup.consentSuffix': ', incluant la suppression automatique après 30 jours.',
	'signup.submit': 'Créer le compte',
	'signup.submitting': 'Création du compte…',
	'signup.hasAccount': 'Vous avez déjà un compte ?',
	'signup.loginLink': 'Se connecter',

	'verify.missingToken': 'Jeton de vérification manquant.',
	'verify.checking': 'Vérification de votre courriel…',
	'verify.successTitle': 'Courriel vérifié 🎉',
	'verify.successPrefix': 'Vous pouvez maintenant',
	'verify.loginLink': 'vous connecter',
	'verify.successSuffix': 'et démarrer une analyse.',
	'verify.failedTitle': 'Échec de la vérification',
	'verify.failedGeneric': 'La vérification a échoué.',
	'verify.failedHint': 'Le lien a peut-être expiré. Essayez de vous réinscrire pour en demander un nouveau.',

	'dashboard.title': 'Vos analyses',
	'dashboard.newAnalysis': 'Nouvelle analyse',
	'dashboard.loading': 'Chargement…',
	'dashboard.loadError': 'Impossible de charger vos tâches. Essayez de rafraîchir la page.',
	'dashboard.emptyNotice': "Vous n'avez pas encore effectué d'analyse d'ascendance.",
	'dashboard.emptyCta': 'Téléversez votre premier fichier de génotypes',
	'dashboard.table.job': 'Tâche',
	'dashboard.table.type': 'Type',
	'dashboard.table.status': 'Statut',
	'dashboard.table.overlap': 'Chevauchement SNP',
	'dashboard.table.submitted': 'Soumis',
	'dashboard.table.view': 'Voir',
	'dashboard.overlapWarningTitle': 'Sous le seuil de fiabilité',

	'upload.title': "Nouvelle analyse d'ascendance",
	'upload.buildNoticePrefix': 'Les génotypes doivent être harmonisés avec',
	'upload.buildNoticeSuffix':
		". La plateforme ne peut pas reconvertir les versions du génome — une version incompatible se traduira par un chevauchement de SNP très faible.",
	'upload.limits.intro': 'Limites :',
	'upload.limits.combined': 'de taille totale téléversée et',
	'upload.limits.samplesRest':
		"échantillons. Les données présentant moins de 1000 SNP en chevauchement avec le panel de référence de Diet Network sont rejetées — envisagez d'abord l'imputation. Les allèles doivent être harmonisés avec le codage/brin du panel de référence ; un échange ou une inversion systématique des allèles est également rejeté, avec une explication.",
	'upload.dropzone.prompt': 'Glissez-déposez vos fichiers .vcf, .vcf.gz, .bgen ou PLINK (.bed/.bim/.fam) ici',
	'upload.dropzone.or': 'ou',
	'upload.dropzone.browse': 'Parcourir les fichiers',
	'upload.dropzone.maxCombined': 'Max {mb} Mo au total',
	'upload.bgen.label': "Fichier d'échantillons (.sample)",
	'upload.bgen.hint': 'Requis pour convertir les génotypes bgen au format PLINK.',
	'upload.plink.bimLabel': 'Fichier de variants (.bim)',
	'upload.plink.famLabel': "Fichier d'échantillons (.fam)",
	'upload.plink.hint':
		'Les génotypes PLINK sont utilisés tels quels (aucune conversion nécessaire) mais passent tout de même par le même filtre de données manquantes que les téléversements VCF/bgen.',
	'upload.consent.prefix': "Je consens au traitement de ces données génétiques pour l'inférence d'ascendance, conformément à la",
	'upload.consent.link': 'politique de confidentialité',
	'upload.consent.suffix':
		'. Je comprends que le fichier brut est supprimé immédiatement après le succès de l’inférence, et que les résultats dérivés sont automatiquement supprimés après 30 jours.',
	'upload.submit': "Lancer l'inférence d'ascendance",
	'upload.submitting': 'Téléversement…',
	'upload.errors.chooseFile': 'Veuillez choisir un fichier de génotypes.',
	'upload.errors.unsupportedType':
		'Type de fichier non pris en charge. Veuillez téléverser un fichier .vcf, .vcf.gz, .bgen ou .bed.',
	'upload.errors.sampleRequired': 'Un fichier .sample est requis avec un téléversement .bgen.',
	'upload.errors.bimFamRequired': 'Un fichier .bim et un fichier .fam sont requis avec un téléversement .bed.',
	'upload.errors.tooLarge': 'La taille totale du téléversement ({size} Mo) dépasse la limite de {max} Mo.',
	'upload.errors.consentRequired': 'Vous devez consentir au traitement avant de téléverser.',
	'upload.errors.uploadFailed': 'Le téléversement a échoué. Veuillez réessayer.',

	'jobDetail.back': '← Retour au tableau de bord',
	'jobDetail.loading': 'Chargement…',
	'jobDetail.loadError': 'Impossible de charger cette tâche.',
	'jobDetail.heading': 'Analyse',
	'jobDetail.queued': 'Votre tâche est en attente',
	'jobDetail.aheadSingular': 'tâche devant vous',
	'jobDetail.aheadPlural': 'tâches devant vous',
	'jobDetail.queuedEmailNotice': 'Nous vous enverrons un courriel dès qu’elle démarrera.',
	'jobDetail.running':
		"Votre tâche est en cours d'exécution. L'ensemble Diet Network exécute 15 modèles séquentiellement, ce qui peut prendre quelques minutes.",
	'jobDetail.autoUpdate': 'Cette page se met à jour automatiquement.',
	'jobDetail.failedGeneric': 'La tâche a échoué.',
	'jobDetail.failedHint':
		'Cela est généralement dû à des données mal formées ou à une version du génome incompatible. Vous pouvez démarrer une nouvelle analyse depuis le tableau de bord.',
	'jobDetail.download': 'Télécharger tous les fichiers de résultats (.zip)',
	'jobDetail.lowOverlapPrefix': 'Faible chevauchement SNP',
	'jobDetail.lowOverlapBody':
		'Les auteurs de Diet Network recommandent d’écarter les prédictions lorsque le chevauchement avec le panel de référence des SNP est inférieur à 1000 SNP. Considérez ces résultats comme non fiables — une cause fréquente est une version du génome autre que GRCh38.',
	'jobDetail.overlapGood': 'Chevauchement SNP avec le panel de référence Diet Network :',

	'support.prefix': 'Si cela semble incorrect,',
	'support.link': 'ouvrez un ticket sur GitHub',

	'status.queued': 'En attente',
	'status.running': 'En cours',
	'status.done': 'Terminé',
	'status.failed': 'Échoué',

	'privacy.title': 'Confidentialité et conservation des données',
	'privacy.collect.title': 'Ce que nous recueillons',
	'privacy.collect.body':
		'Votre courriel de compte, ainsi que le fichier de génotypes (VCF ou bgen) que vous choisissez de téléverser pour l’inférence d’ascendance, ainsi que les prédictions d’ascendance dérivées.',
	'privacy.why.title': 'Pourquoi',
	'privacy.why.body':
		"Uniquement pour exécuter le modèle d'inférence d'ascendance Diet Network en votre nom et vous montrer les résultats. Nous n'utilisons vos données à aucune autre fin, et nous ne les vendons ni ne les partageons.",
	'privacy.where.title': 'Où elles sont stockées',
	'privacy.where.body':
		"Sur un stockage chiffré au sein de l'infrastructure infonuagique de recherche canadienne (Arbutus / Alliance de recherche numérique du Canada). Tout le traitement se déroule au Canada.",
	'privacy.retention.title': 'Conservation',
	'privacy.retention.body1':
		'Votre fichier de génotypes brut téléversé est supprimé immédiatement une fois l’inférence terminée avec succès — c’est l’élément le plus sensible, et il n’est plus nécessaire une fois les prédictions obtenues. Les résultats dérivés (prédictions et chevauchement SNP) sont conservés pendant',
	'privacy.retention.days': '30 jours',
	'privacy.retention.body2':
		'à partir du téléversement, puis supprimés définitivement par une tâche automatisée quotidienne. Vous pouvez également demander une suppression anticipée.',
	'privacy.rights.title': 'Vos droits',
	'privacy.rights.body':
		"Vous ne pouvez accéder qu'à vos propres téléversements et résultats. En vertu de la Loi 25 du Québec et de la LPRPDE, vous pouvez demander l'accès, la correction ou la suppression de vos renseignements personnels en tout temps en contactant l'exploitant de la plateforme.",

	'localeSwitcher.label': 'Changer de langue'
};
