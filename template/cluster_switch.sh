function ic-cluster {
    alias runai=runai-ic
    # This is actually changing the context not the cluster ...
    runai config cluster ic-caas
    runai config project mlo-$GASPAR_USERNAME
}

function rcp-prod-cluster {
    alias runai=runai-rcp-prod
    # This is actually changing the context not the cluster ...
    runai config cluster rcp-caas-prod
    runai config project mlo-$GASPAR_USERNAME
}
